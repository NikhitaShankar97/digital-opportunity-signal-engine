from __future__ import annotations
import numpy as np
import pandas as pd


def _percentile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    rank = series.rank(method="average", pct=True)
    return (rank if higher_is_better else 1 - rank + (1 / len(series))) * 100


def score_peers(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    complete = df[df.record_status.eq("complete")].copy()
    minimum = int(config["minimum_peer_count"])
    if len(complete) < minimum:
        out = df.copy()
        out["opportunity_score"] = np.nan
        out["confidence_score"] = out.apply(lambda r: _confidence(r, config, len(complete)), axis=1)
        out["classification"] = "Insufficient peer evidence"
        out["signal_explanation"] = f"Scoring paused: {len(complete)} of {minimum} required peer observations are complete."
        return out

    p = pd.DataFrame(index=complete.index)
    p["momentum"] = _percentile(complete.mom_change_pct)
    p["engagement_depth"] = (
        _percentile(complete.pages_per_visit) +
        _percentile(complete.avg_visit_duration_seconds) +
        _percentile(complete.bounce_rate_pct, higher_is_better=False)
    ) / 3
    p["traffic_scale"] = _percentile(complete.monthly_visits)
    weights = config["weights"]
    complete["opportunity_score"] = sum(p[k] * float(v) for k, v in weights.items())
    complete["confidence_score"] = complete.apply(lambda r: _confidence(r, config, len(complete)), axis=1)
    t = config["classification_thresholds"]
    complete["classification"] = np.select(
        [complete.opportunity_score >= t["priority"], complete.opportunity_score >= t["investigate"]],
        ["Priority", "Investigate"], default="Watch"
    )
    complete["signal_explanation"] = complete.apply(
        lambda r: f"{r['company']} combines {r['mom_change_pct']:+.1f}% monthly traffic change with "
                  f"{r['pages_per_visit']:.2f} pages per visit; classification is peer-relative, not investment advice.", axis=1
    )
    pending = df[~df.record_status.eq("complete")].copy()
    pending["opportunity_score"] = np.nan
    pending["confidence_score"] = pending.apply(lambda r: _confidence(r, config, len(complete)), axis=1)
    pending["classification"] = "Data pending"
    pending["signal_explanation"] = "Public observation is incomplete; no score produced."
    return pd.concat([complete, pending]).sort_index()


def _confidence(row: pd.Series, config: dict, peer_count: int) -> float:
    fields = config["confidence"]["required_metrics"]
    completeness = sum(pd.notna(row.get(f)) for f in fields) / len(fields)
    peer_coverage = min(peer_count / config["confidence"]["peer_count_target"], 1)
    source = config["confidence"].get("source_reliability", 0.60)
    history = min(config["confidence"].get("history_months_observed", 1) /
                  config["confidence"].get("history_months_target", 3), 1)
    return round(100 * (0.50 * completeness + 0.20 * peer_coverage + 0.15 * source + 0.15 * history), 1)
