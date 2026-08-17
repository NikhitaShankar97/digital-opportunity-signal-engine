from pathlib import Path
import pandas as pd


def load_observations(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["collection_date"])


def load_country_traffic(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)

