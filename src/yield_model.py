"""
Data-driven cross-check using REAL historical Odisha crop statistics
(1997-2019, Govt of India Crop Production Statistics, via the RF repo).

Important honesty note about this dataset (so the UI can say this to
the user rather than imply false precision): the 'Fertilizer' and
'Pesticide' columns in this public dataset are state-level fertilizer/
pesticide *consumption* apportioned across crops by cultivated area --
not a measured per-crop dose. So this module is used to show a real
historical yield-vs-fertilizer-intensity relationship for the selected
crop in Odisha (useful context / sanity check), NOT as the source of
the recommended dose itself. The recommended dose comes from
fertilizer_reference.py (ICAR/CRRI/OUAT package-of-practice figures).
"""

from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "odisha_crop_yield_state.csv"
RECENT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "odisha_recent_official_yield.csv"

_df_cache = None


def load_odisha_data() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        df = pd.read_csv(DATA_PATH)
        df["fert_per_ha"] = df["Fertilizer"] / df["Area"]
        df["pest_per_ha"] = df["Pesticide"] / df["Area"]
        _df_cache = df
    return _df_cache


def load_recent_official_data() -> pd.DataFrame:
    """Return newer official anchor observations kept separate from model data."""
    return pd.read_csv(RECENT_DATA_PATH)


def list_crops():
    return sorted(load_odisha_data()["Crop"].unique().tolist())


def crop_history(crop: str) -> pd.DataFrame:
    df = load_odisha_data()
    return df[df["Crop"] == crop].sort_values("Crop_Year")


def fit_yield_trend(crop: str):
    """
    Fit a small RandomForest on real historical rows for this crop:
    Yield ~ fert_per_ha, Annual_Rainfall, pest_per_ha
    Returns (model, feature_names, r2_on_train, n_rows) or None if too
    little real data exists for this crop to fit anything meaningful.
    """
    hist = crop_history(crop)
    if len(hist) < 15:
        return None
    X = hist[["fert_per_ha", "Annual_Rainfall", "pest_per_ha"]]
    y = hist["Yield"]
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    model.fit(X, y)
    r2 = model.score(X, y)
    return model, ["fert_per_ha", "Annual_Rainfall", "pest_per_ha"], r2, len(hist)


def predict_yield(crop: str, fert_per_ha: float, rainfall_mm: float, pest_per_ha: float):
    fit = fit_yield_trend(crop)
    if fit is None:
        return None
    model, feats, r2, n = fit
    x = pd.DataFrame([[fert_per_ha, rainfall_mm, pest_per_ha]], columns=feats)
    pred = model.predict(x)[0]
    return {"predicted_yield": round(float(pred), 4), "r2_on_history": round(r2, 3),
            "n_historical_rows": n}
