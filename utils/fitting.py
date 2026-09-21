"""Build and fit pypricing demand models from Streamlit choices."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from utils.pymc_compat import skip_pymc_marketing_mmm_import

skip_pymc_marketing_mmm_import()
from pypricing import (
    CrossElasticitySpec,
    LogLogDemandModel,
    PanelColumns,
    QuadraticLogDemandModel,
    SigmoidSaturationDemandModel,
)

SamplerName = Literal["nutpie", "pymc"]

MODEL_CLASSES = {
    "Log-log (constant elasticity)": LogLogDemandModel,
    "Quadratic in log-price": QuadraticLogDemandModel,
    "Sigmoid saturation": SigmoidSaturationDemandModel,
}

MODEL_HELP = {
    "Log-log (constant elasticity)": (
        "Own-price elasticity is constant across the price range. "
        "Revenue-optimal prices usually sit on the bound you set."
    ),
    "Quadratic in log-price": (
        "Elasticity can change with price (discount vs full price). "
        "Better when you expect an interior revenue peak."
    ),
    "Sigmoid saturation": (
        "Demand flattens at extreme prices. Local elasticity varies along the curve."
    ),
}


def build_panel_columns(
    *,
    control_columns: list[str] | None,
    group_columns: list[str] | None,
    region_col: str | None = None,
    quantity_floor: float = 1.0,
) -> PanelColumns:
    controls = tuple(control_columns) if control_columns else None
    groups = tuple(group_columns) if group_columns else None
    return PanelColumns(
        control_columns=controls,
        group_columns=groups,
        region_col=region_col or None,
        quantity_floor=quantity_floor,
    )


def build_model(
    model_label: str,
    *,
    panel_columns: PanelColumns,
    cross_mode: str | None,
    cross_group_level: int | None,
):
    cls = MODEL_CLASSES[model_label]
    cross = None
    if cross_mode == "within_group":
        cross = CrossElasticitySpec(mode="within_group", group_level=cross_group_level)
    elif cross_mode == "all":
        cross = CrossElasticitySpec(mode="all")
    return cls(panel_columns=panel_columns, cross_elasticity=cross)


def nutpie_available() -> bool:
    try:
        import nutpie  # noqa: F401
    except ImportError:
        return False
    return True


def default_sampler() -> SamplerName:
    return "nutpie" if nutpie_available() else "pymc"


def build_sample_kwargs(
    *,
    sampler: SamplerName,
    draws: int,
    tune: int,
    chains: int,
    random_seed: int,
    target_accept: float,
) -> dict[str, Any]:
    """Kwargs forwarded to ``DemandModel.fit`` / ``pm.sample``."""
    kwargs: dict[str, Any] = {
        "draws": draws,
        "tune": tune,
        "chains": chains,
        "random_seed": random_seed,
        "progressbar": False,
        "nuts_sampler": sampler,
    }
    if sampler == "nutpie":
        # PyMC 5.28 reads nutpie target_accept from nuts={}, not the top-level kwarg.
        kwargs["nuts"] = {"target_accept": target_accept}
    else:
        kwargs["cores"] = 1
        kwargs["target_accept"] = target_accept
    return kwargs


def fit_model(model, df: pd.DataFrame, sample_kwargs: dict[str, Any]):
    return model.fit(df, **sample_kwargs)


def controls_for_sku(df: pd.DataFrame, model, sku) -> dict[str, float] | None:
    names = list(model.control_names_ or ())
    if not names:
        return None
    sub = df.loc[df[model.sku_col] == sku, names]
    if sub.empty:
        raise ValueError(f"No rows for sku={sku!r}")
    return {c: float(sub[c].median()) for c in names}


def controls_df_for_opt(df: pd.DataFrame, model) -> pd.DataFrame | None:
    names = list(model.control_names_ or ())
    if not names:
        return None
    return df.groupby(model.sku_col, as_index=False)[names].median()
