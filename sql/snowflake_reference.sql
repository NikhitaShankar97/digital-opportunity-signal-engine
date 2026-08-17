-- Production reference only; Snowflake is not required by the free POC.
CREATE OR REPLACE TABLE ANALYTICS.COMPANY_SIGNALS AS
SELECT
  LOWER($1:domain::STRING) AS domain,
  $1:observation_month::STRING AS observation_month,
  $1:monthly_visits::FLOAT AS monthly_visits,
  $1:mom_change_pct::FLOAT AS mom_change_pct,
  $1:record_status::STRING AS record_status,
  CURRENT_TIMESTAMP() AS processed_at
FROM @SIMILARWEB_RAW_STAGE (FILE_FORMAT => JSON_FILE_FORMAT);

