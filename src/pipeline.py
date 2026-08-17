from pathlib import Path
import pandas as pd
import yaml
from src.ingestion import load_observations
from src.validation import validate_observations
from src.scoring import score_peers


def run(root: str | Path = ".") -> tuple[pd.DataFrame, list[dict]]:
    root = Path(root)
    df = load_observations(root / "data/raw/similarweb_observations.csv")
    config = yaml.safe_load((root / "config/scoring_rules.yml").read_text())
    issues = validate_observations(df)
    scored = score_peers(df, config)
    output = root / "data/processed/company_signals.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(output, index=False)
    return scored, issues


if __name__ == "__main__":
    run()

