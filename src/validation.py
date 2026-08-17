import pandas as pd

PERCENT_FIELDS = [
    "bounce_rate_pct", "organic_search_share_pct",
    "organic_search_within_search_pct", "paid_search_within_search_pct",
]
POSITIVE_FIELDS = ["monthly_visits", "pages_per_visit", "avg_visit_duration_seconds"]


def validate_observations(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    keys = ["domain", "observation_month"]
    for _, row in df[df.duplicated(keys, keep=False)].iterrows():
        issues.append({"domain": row.domain, "severity": "error", "code": "duplicate_observation"})
    for _, row in df.iterrows():
        complete = row.get("record_status") == "complete"
        for field in PERCENT_FIELDS:
            value = row.get(field)
            if pd.notna(value) and not 0 <= value <= 100:
                issues.append({"domain": row.domain, "severity": "error", "code": f"invalid_{field}"})
        for field in POSITIVE_FIELDS:
            value = row.get(field)
            if pd.notna(value) and value < 0:
                issues.append({"domain": row.domain, "severity": "error", "code": f"negative_{field}"})
        if complete:
            required = POSITIVE_FIELDS + ["mom_change_pct", "bounce_rate_pct"]
            for field in required:
                if pd.isna(row.get(field)):
                    issues.append({"domain": row.domain, "severity": "error", "code": f"missing_{field}"})
        else:
            issues.append({"domain": row.domain, "severity": "warning", "code": str(row.get("record_status"))})
    return issues

