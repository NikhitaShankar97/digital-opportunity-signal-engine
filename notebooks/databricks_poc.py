# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC ### Similarweb Investment Signal Engine: Free Edition Proof of Concept
# MAGIC
# MAGIC This notebook processes and validates publicly available Similarweb estimates collected for a three-company analysis. The proof of concept uses CSV files as its input. A production implementation would replace the manual CSV input with a licensed Similarweb API or data feed while retaining the downstream validation and processing logic.
# MAGIC

# COMMAND ----------

from pyspark.sql import functions as F

input_path = "/Volumes/workspace/similarweb_poc/raw/similarweb_observations.csv"
observations = (spark.read.option("header", True).option("inferSchema", True).csv(input_path)
    .withColumn("domain", F.lower(F.trim("domain"))))

# COMMAND ----------

quality = observations.select(
    F.count("*").alias("rows"),
    F.countDistinct("domain", "observation_month").alias("distinct_keys"),
    F.sum(F.when(~F.col("bounce_rate_pct").between(0, 100), 1).otherwise(0)).alias("invalid_bounce_rates"),
    F.sum(F.when(F.col("monthly_visits") < 0, 1).otherwise(0)).alias("negative_visits"),
)
display(quality)

# COMMAND ----------

score_eligible = observations.filter(F.col("record_status") == "complete")
display(score_eligible.orderBy(F.col("mom_change_pct").desc()))

# COMMAND ----------

# Persist only after quality checks pass.
assert quality.first()["rows"] == quality.first()["distinct_keys"]
assert quality.first()["invalid_bounce_rates"] == 0
assert quality.first()["negative_visits"] == 0

(score_eligible.write.mode("overwrite")
    .format("delta")
    .saveAsTable("workspace.similarweb_poc.validated_observations"))


# COMMAND ----------

country_path = "/Volumes/workspace/similarweb_poc/raw/country_traffic.csv"

country_traffic = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(country_path)
    .withColumn("domain", F.lower(F.trim("domain")))
)

country_quality = country_traffic.select(
    F.count("*").alias("rows"),
    F.countDistinct(
        "domain", "observation_month", "country"
    ).alias("distinct_keys"),
    F.sum(
        F.when(
            ~F.col("desktop_traffic_share_pct").between(0, 100), 1
        ).otherwise(0)
    ).alias("invalid_traffic_shares")
)

display(country_quality)
display(country_traffic.orderBy("domain", F.col("desktop_traffic_share_pct").desc()))

quality_result = country_quality.first()

assert quality_result["rows"] == quality_result["distinct_keys"]
assert quality_result["invalid_traffic_shares"] == 0

(
    country_traffic.write
    .mode("overwrite")
    .format("delta")
    .saveAsTable("workspace.similarweb_poc.validated_country_traffic")
)

# COMMAND ----------

demographics_path = "/Volumes/workspace/similarweb_poc/raw/audience_demographics.csv"

demographics = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(demographics_path)
    .withColumn("domain", F.lower(F.trim("domain")))
)

demographics_quality = demographics.select(
    F.count("*").alias("rows"),
    F.countDistinct(
        "domain", "observation_month"
    ).alias("distinct_keys"),
    F.sum(
        F.when(~F.col("female_pct").between(0, 100), 1).otherwise(0)
    ).alias("invalid_female_pct"),
    F.sum(
        F.when(~F.col("male_pct").between(0, 100), 1).otherwise(0)
    ).alias("invalid_male_pct"),
    F.sum(
        F.when(
            F.abs(F.col("female_pct") + F.col("male_pct") - 100) > 0.01,
            1
        ).otherwise(0)
    ).alias("invalid_gender_totals")
)

display(demographics_quality)
display(demographics.orderBy("domain"))

quality_result = demographics_quality.first()

assert quality_result["rows"] == quality_result["distinct_keys"]
assert quality_result["invalid_female_pct"] == 0
assert quality_result["invalid_male_pct"] == 0
assert quality_result["invalid_gender_totals"] == 0

(
    demographics.write
    .mode("overwrite")
    .format("delta")
    .saveAsTable("workspace.similarweb_poc.validated_audience_demographics")
)

# COMMAND ----------

from pyspark.sql.window import Window

peer_count = score_eligible.count()


# Converting each metric into a score from roughly 0 to 100.
# The score shows how each company performs relative to the other
# companies in this analysis.
def add_percentile_score(
    df,
    source_column,
    output_column,
    higher_is_better=True
):
    # Rank companies within the same observation month.
    order_window = (
        Window
        .partitionBy("observation_month")
        .orderBy(F.col(source_column))
    )

    tie_window = Window.partitionBy(
        "observation_month",
        source_column
    )

    # Companies with the same value receive the same average rank.
    average_rank = (
        F.rank().over(order_window)
        + (F.count("*").over(tie_window) - 1) / 2
    )

    if higher_is_better:
        score = average_rank / F.lit(peer_count) * 100
    else:
        # A lower bounce rate is better, so its ranking is reversed.
        score = (
            F.lit(peer_count + 1) - average_rank
        ) / F.lit(peer_count) * 100

    return df.withColumn(output_column, score)


# Traffic momentum measures whether website traffic is growing or declining compared with the previous month.
scored = add_percentile_score(
    score_eligible,
    "mom_change_pct",
    "momentum_score"
)

# Engagement is based on pages viewed, visit duration and bounce rate.
scored = add_percentile_score(
    scored,
    "pages_per_visit",
    "pages_score"
)

scored = add_percentile_score(
    scored,
    "avg_visit_duration_seconds",
    "duration_score"
)

scored = add_percentile_score(
    scored,
    "bounce_rate_pct",
    "bounce_score",
    higher_is_better=False
)

# Traffic scale represents the size of the website's audience.
scored = add_percentile_score(
    scored,
    "monthly_visits",
    "traffic_scale_score"
)


# Momentum receives the highest weight because the goal is to identify companies showing emerging digital growth, not only the largest website.
# Engagement is weighted next because traffic growth is more meaningful when visitors stay longer and explore more pages.
# Traffic scale still matters, but receives the lowest weight so that a large established website does not automatically rank first.
momentum_weight = 0.40
engagement_weight = 0.35
traffic_scale_weight = 0.25


scored = (
    scored
    # Average the three visitor-engagement measures.
    .withColumn(
        "engagement_depth_score",
        (
            F.col("pages_score")
            + F.col("duration_score")
            + F.col("bounce_score")
        ) / 3
    )
    # Final score =
    # 40% momentum + 35% engagement + 25% traffic scale.
    .withColumn(
        "opportunity_score",
        F.round(
            F.col("momentum_score") * momentum_weight
            + F.col("engagement_depth_score") * engagement_weight
            + F.col("traffic_scale_score") * traffic_scale_weight,
            2
        )
    )
    # Confidence is 84% because the required metrics are complete,
    # but the POC currently uses one month of public estimate data.
    .withColumn("confidence_score", F.lit(84.0))
    # Convert the numeric score into a simple research category.
    .withColumn(
        "classification",
        F.when(
            F.col("opportunity_score") >= 70,
            "Priority"
        )
        .when(
            F.col("opportunity_score") >= 45,
            "Investigate"
        )
        .otherwise("Watch")
    )
)


final_scores = scored.select(
    "domain",
    "company",
    "observation_month",
    F.round("momentum_score", 2).alias("momentum_score"),
    F.round("engagement_depth_score", 2).alias("engagement_depth_score"),
    F.round("traffic_scale_score", 2).alias("traffic_scale_score"),
    F.round("opportunity_score", 2).alias("opportunity_score"),
    "confidence_score",
    "classification"
)

display(
    final_scores
    .orderBy(F.col("opportunity_score").desc())
)

# Save the results so they can be reused by SQL queries,
# dashboards and the Streamlit application.
(
    final_scores.write
    .mode("overwrite")
    .format("delta")
    .saveAsTable(
        "workspace.similarweb_poc.opportunity_scores"
    )
)