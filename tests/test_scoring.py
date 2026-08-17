import pandas as pd
from src.scoring import score_peers


def test_scoring_pauses_below_minimum_peer_count():
    df = pd.DataFrame([{"domain": "a.com", "company": "A", "record_status": "complete", "monthly_visits": 1,
                        "mom_change_pct": 1, "bounce_rate_pct": 40, "pages_per_visit": 2,
                        "avg_visit_duration_seconds": 60, "organic_search_share_pct": 20}])
    config = {"minimum_peer_count": 3, "confidence": {"required_metrics": ["monthly_visits"], "peer_count_target": 3}}
    result = score_peers(df, config)
    assert result.opportunity_score.isna().all()
    assert result.classification.eq("Insufficient peer evidence").all()

