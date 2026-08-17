import pandas as pd
from src.validation import validate_observations


def test_impossible_percentage_is_rejected():
    df = pd.DataFrame([{"domain": "x.com", "observation_month": "2026-07", "record_status": "pending", "bounce_rate_pct": 101}])
    assert any(i["code"] == "invalid_bounce_rate_pct" for i in validate_observations(df))


def test_pending_record_is_warning_not_fabricated():
    df = pd.DataFrame([{"domain": "x.com", "observation_month": "2026-07", "record_status": "pending_public_limit"}])
    issues = validate_observations(df)
    assert issues == [{"domain": "x.com", "severity": "warning", "code": "pending_public_limit"}]

