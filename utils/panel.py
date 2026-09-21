"""Demo panel generation and CSV normalisation for pypricing."""

from __future__ import annotations

from typing import Any

import pandas as pd

REQUIRED = ("sku", "price", "quantity")
OPTIONAL_KEYS = ("period", "region")

_NAME_ALIASES = {
    "sku": ("sku", "product", "item", "product_id", "sku_id"),
    "price": ("price", "unit_price", "avg_price", "list_price"),
    "quantity": ("quantity", "qty", "units", "demand", "volume", "sales_units"),
    "period": ("period", "date", "week", "week_start", "ds", "time"),
    "region": ("region", "market", "geo", "country"),
}


def guess_column(columns: list[str], key: str) -> str | None:
    lowered = {c.lower().strip(): c for c in columns}
    for alias in _NAME_ALIASES.get(key, (key,)):
        if alias in lowered:
            return lowered[alias]
    return None


def generate_demo_panel(
    *,
    n_periods: int = 26,
    n_skus: int = 6,
    n_controls: int = 1,
    n_categories: int = 2,
    shape: str = "log_log",
    random_state: int = 0,
    include_seasonality: bool = True,
) -> pd.DataFrame:
    from utils.pymc_compat import skip_pymc_marketing_mmm_import

    skip_pymc_marketing_mmm_import()
    from pypricing.synthetic_data import generate_mock_data

    kwargs: dict = dict(
        n_skus=n_skus,
        n_controls=n_controls,
        shape=shape,
        random_state=random_state,
        include_seasonality=include_seasonality,
        freq="W",
    )
    # hierarchy_levels writes category_1, category_2, … (needed for partial pooling / cross-price).
    n_cat = min(int(n_categories), int(n_skus))
    if n_cat >= 2:
        kwargs["hierarchy_levels"] = (n_cat,)
    return generate_mock_data(n_periods, **kwargs)


def canonicalize_panel(
    df: pd.DataFrame,
    mapping: dict[str, str | None],
) -> pd.DataFrame:
    """Rename mapped columns to pypricing defaults; leave other columns intact."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    rename: dict[str, str] = {}
    used_targets: set[str] = set()
    for target in (*REQUIRED, *OPTIONAL_KEYS):
        src = mapping.get(target)
        if not src or src not in out.columns:
            continue
        if src == target:
            used_targets.add(target)
            continue
        if target in out.columns and src != target:
            out = out.rename(columns={target: f"{target}_original"})
        rename[src] = target
        used_targets.add(target)
    out = out.rename(columns=rename)

    missing = [c for c in REQUIRED if c not in out.columns]
    if missing:
        raise ValueError(f"Mapped panel is missing required columns: {missing}")

    out["sku"] = out["sku"].astype(str)
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce")
    if "period" in out.columns:
        parsed = pd.to_datetime(out["period"], errors="coerce")
        if parsed.notna().mean() > 0.8:
            out["period"] = parsed
    return out


def panel_summary(df: pd.DataFrame) -> dict[str, Any]:
    n_sku = int(df["sku"].nunique())
    price = df["price"]
    qty = df["quantity"]
    out: dict[str, Any] = {
        "rows": len(df),
        "skus": n_sku,
        "price_min": float(price.min()) if len(df) else None,
        "price_max": float(price.max()) if len(df) else None,
        "qty_min": float(qty.min()) if len(df) else None,
        "qty_max": float(qty.max()) if len(df) else None,
        "zero_qty_share": float((qty <= 0).mean()) if len(df) else 0.0,
        "nonpositive_price": int((price <= 0).sum()) if len(df) else 0,
        "periods": int(df["period"].nunique()) if "period" in df.columns else None,
    }
    return out


_DERIVED = {"log_price", "log_quantity"}


def numeric_candidate_columns(df: pd.DataFrame) -> list[str]:
    reserved = {"sku", "price", "quantity", "period", "region", *_DERIVED}
    cols = []
    for col in df.columns:
        if col in reserved:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            cols.append(col)
    return cols


def group_candidate_columns(df: pd.DataFrame) -> list[str]:
    reserved = {"sku", "price", "quantity", "period", *_DERIVED}
    cols = []
    for col in df.columns:
        if col in reserved:
            continue
        nunique = df[col].nunique(dropna=True)
        if 1 < nunique < min(50, max(3, len(df) // 2)):
            cols.append(col)
    return cols


def default_control_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if str(c).startswith("control_")]


def default_group_columns(df: pd.DataFrame) -> list[str]:
    return [
        c
        for c in df.columns
        if str(c) == "category" or str(c).startswith("category_")
    ]
