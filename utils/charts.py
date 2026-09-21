"""Plotly charts from a fitted pypricing model (no matplotlib in the UI)."""

from __future__ import annotations

import arviz as az
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _hdi_bounds(draws: np.ndarray, hdi_prob: float) -> tuple[float, float]:
    hdi = az.hdi(np.asarray(draws).ravel(), hdi_prob=hdi_prob)
    if hasattr(hdi, "sel"):
        return float(hdi.sel(hdi="lower").values), float(hdi.sel(hdi="higher").values)
    arr = np.asarray(hdi).reshape(-1)
    return float(arr[0]), float(arr[1])


def _layout(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10), legend=dict(yanchor="top", y=0.99))
    return fig


def _band(
    x,
    mean,
    lower,
    upper,
    *,
    xlabel: str,
    ylabel: str,
    title: str,
    hdi_prob: float,
    hover: str | None = None,
) -> go.Figure:
    x = list(x)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=list(upper),
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=list(lower),
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            name=f"{int(hdi_prob * 100)}% HDI",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=list(mean),
            mode="lines+markers",
            name="Posterior mean",
            hovertemplate=hover or "%{x:.3g}<br>%{y:.3g}<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title=xlabel, yaxis_title=ylabel, title=title)
    return _layout(fig)


def elasticity_forest(model, *, hdi_prob: float = 0.9) -> go.Figure:
    post = model.idata.posterior["elasticity_sku"]
    sku_codes = list(post.coords["sku"].values)
    labels = (
        [str(x) for x in model.sku_levels_]
        if model.sku_levels_ is not None and len(model.sku_levels_) == len(sku_codes)
        else [str(x) for x in sku_codes]
    )
    means, lowers, uppers = [], [], []
    for code in sku_codes:
        draws = post.sel(sku=code).values.flatten()
        means.append(float(np.mean(draws)))
        lo, hi = _hdi_bounds(draws, hdi_prob)
        lowers.append(lo)
        uppers.append(hi)

    order = np.argsort(means)
    labels = [labels[i] for i in order]
    means = [means[i] for i in order]
    lowers = [lowers[i] for i in order]
    uppers = [uppers[i] for i in order]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=means,
            y=labels,
            mode="markers",
            error_x=dict(
                type="data",
                symmetric=False,
                array=[u - m for u, m in zip(uppers, means)],
                arrayminus=[m - lo for lo, m in zip(lowers, means)],
            ),
            name="Posterior mean",
            hovertemplate="%{y}<br>elasticity %{x:.3f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_dash="dot", line_color="gray")
    fig.add_vline(x=-1, line_dash="dash", line_color="lightgray")
    fig.update_layout(
        xaxis_title="Own-price elasticity",
        yaxis_title="SKU",
        title=f"Own-price elasticity ({int(hdi_prob * 100)}% HDI)",
        showlegend=False,
    )
    return _layout(fig, height=max(280, 28 * len(labels) + 80))


def multiplier_forest(summary: pd.DataFrame, *, pct: int, hdi_prob: float) -> go.Figure:
    df = summary.reset_index() if "sku" not in summary.columns else summary.copy()
    mean_col = next(c for c in df.columns if c.endswith("_mean") or c == "quantity_multiplier_mean")
    lo_col = next(c for c in df.columns if "hdi_lower" in c)
    hi_col = next(c for c in df.columns if "hdi_upper" in c)
    sku_col = "sku" if "sku" in df.columns else df.columns[0]
    df = df.sort_values(mean_col)
    means = df[mean_col].to_numpy(dtype=float)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=means,
            y=df[sku_col].astype(str),
            mode="markers",
            error_x=dict(
                type="data",
                symmetric=False,
                array=df[hi_col].to_numpy(dtype=float) - means,
                arrayminus=means - df[lo_col].to_numpy(dtype=float),
            ),
            name="Posterior mean",
            hovertemplate="%{y}<br>qty × %{x:.3f}<extra></extra>",
        )
    )
    fig.add_vline(x=1.0, line_dash="dot", line_color="gray")
    fig.update_layout(
        xaxis_title="Quantity multiplier",
        yaxis_title="SKU",
        title=f"Quantity change for a {pct:+d}% price move ({int(hdi_prob * 100)}% HDI)",
        showlegend=False,
    )
    return _layout(fig, height=max(280, 28 * len(df) + 80))


def _grid_frame(model, sku, price_grid, controls: dict[str, float] | None) -> pd.DataFrame:
    prices = np.asarray(list(price_grid), dtype=float)
    out = pd.DataFrame({model.sku_col: sku, model.price_col: prices})
    if model.control_names_:
        if not controls:
            raise ValueError("Model has controls; pass a control dict.")
        for name in model.control_names_:
            out[name] = float(controls[name])
    return out


def response_curve(model, *, sku, price_grid, controls, hdi_prob: float) -> go.Figure:
    pred = model.predict(_grid_frame(model, sku, price_grid, controls), hdi_prob=hdi_prob, random_seed=0)
    p = pred[model.price_col]
    return _band(
        p,
        pred["quantity_mean"],
        pred["quantity_hdi_lower"],
        pred["quantity_hdi_upper"],
        xlabel="Price",
        ylabel="Quantity",
        title=f"Predicted demand · {model.sku_col}={sku}",
        hdi_prob=hdi_prob,
        hover="price %{x:.3g}<br>qty %{y:.3g}<extra></extra>",
    )


def revenue_curve(model, *, sku, price_grid, controls, hdi_prob: float) -> go.Figure:
    pred = model.predict(_grid_frame(model, sku, price_grid, controls), hdi_prob=hdi_prob, random_seed=0)
    p = pred[model.price_col].to_numpy(dtype=float)
    return _band(
        p,
        p * pred["quantity_mean"].to_numpy(dtype=float),
        p * pred["quantity_hdi_lower"].to_numpy(dtype=float),
        p * pred["quantity_hdi_upper"].to_numpy(dtype=float),
        xlabel="Price",
        ylabel="Revenue (price × quantity)",
        title=f"Predicted revenue · {model.sku_col}={sku}",
        hdi_prob=hdi_prob,
        hover="price %{x:.3g}<br>revenue %{y:.3g}<extra></extra>",
    )


def local_elasticity_curve(model, *, sku, price_grid, controls, hdi_prob: float) -> go.Figure:
    from pypricing.plotting import (
        _posterior_local_elasticity,
        _sku_price_grid_design,
    )

    prices, log_price, obs_sku_idx, x_control, sku_value = _sku_price_grid_design(
        model, sku, price_grid, controls
    )
    elast = _posterior_local_elasticity(
        model, log_price=log_price, obs_sku_idx=obs_sku_idx, X_control=x_control
    )
    mean = elast.mean(axis=(0, 1))
    lowers = np.empty(len(mean), dtype=float)
    uppers = np.empty(len(mean), dtype=float)
    for i in range(len(mean)):
        lowers[i], uppers[i] = _hdi_bounds(elast[:, :, i], hdi_prob)
    fig = _band(
        prices,
        mean,
        lowers,
        uppers,
        xlabel="Price",
        ylabel="Local elasticity (dμ / d log p)",
        title=f"Local own-price elasticity · {model.sku_col}={sku_value}",
        hdi_prob=hdi_prob,
        hover="price %{x:.3g}<br>elasticity %{y:.3f}<extra></extra>",
    )
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.add_hline(y=-1, line_dash="dash", line_color="lightgray")
    return fig


def calibration_scatter(preds: pd.DataFrame, quantity_col: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=preds[quantity_col],
            y=preds["quantity_mean"],
            mode="markers",
            name="SKU–period",
            opacity=0.7,
            hovertemplate="observed %{x:.3g}<br>predicted %{y:.3g}<extra></extra>",
        )
    )
    lo = float(min(preds[quantity_col].min(), preds["quantity_mean"].min()))
    hi = float(max(preds[quantity_col].max(), preds["quantity_mean"].max()))
    fig.add_trace(
        go.Scatter(
            x=[lo, hi],
            y=[lo, hi],
            mode="lines",
            name="y = x",
            line=dict(dash="dash", color="gray"),
        )
    )
    fig.update_layout(
        xaxis_title="Observed quantity",
        yaxis_title="Predicted mean quantity",
        title="Calibration: observed vs predicted",
    )
    return _layout(fig)


def ppc_series(preds: pd.DataFrame, model, *, hdi_prob: float) -> go.Figure:
    work = preds.copy()
    sort_cols = [c for c in (model.period_col, model.sku_col) if c in work.columns]
    if sort_cols:
        work = work.sort_values(sort_cols, kind="mergesort").reset_index(drop=True)
    x = np.arange(len(work))
    hover = work.apply(
        lambda r: "<br>".join(f"{c}={r[c]}" for c in sort_cols) if sort_cols else f"obs {r.name}",
        axis=1,
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=work["quantity_hdi_upper"],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=work["quantity_hdi_lower"],
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            name=f"{int(hdi_prob * 100)}% HDI",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=work["quantity_mean"],
            mode="lines",
            name="Posterior mean",
            customdata=hover,
            hovertemplate="%{customdata}<br>mean %{y:.3g}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=work[model.quantity_col],
            mode="markers",
            name="Observed",
            customdata=hover,
            hovertemplate="%{customdata}<br>observed %{y:.3g}<extra></extra>",
        )
    )
    xlab = "Observation index"
    if sort_cols:
        xlab += f" (sorted by {', '.join(sort_cols)})"
    fig.update_layout(xaxis_title=xlab, yaxis_title=model.quantity_col, title="Posterior predictive check")
    return _layout(fig, height=460)


def cross_price_heatmap(model, *, agg: str = "mean") -> go.Figure:
    if model.cross_elasticity is None or "gamma_pair" not in model.idata.posterior:
        raise ValueError("Model was not fit with cross-price terms.")
    pf = model.cross_pairs_
    sku_levels = list(model.sku_levels_)
    n = len(sku_levels)
    gam = model.idata.posterior["gamma_pair"].values
    g_summary = gam.mean(axis=(0, 1)) if agg == "mean" else np.median(gam.reshape(-1, gam.shape[-1]), axis=0)
    mat = np.full((n, n), np.nan, dtype=float)
    for p in range(pf.n_pairs):
        mat[int(pf.pair_from[p]), int(pf.pair_to[p])] = float(g_summary[p])
    labels = [str(s) for s in sku_levels]
    finite = mat[np.isfinite(mat)]
    vmax = float(np.nanmax(np.abs(finite))) if finite.size else 1.0
    fig = go.Figure(
        go.Heatmap(
            z=mat,
            x=labels,
            y=labels,
            colorscale="RdBu_r",
            zmid=0,
            zmin=-vmax,
            zmax=vmax,
            hoverongaps=False,
            colorbar=dict(title="γ"),
            hovertemplate="focal %{y}<br>competitor %{x}<br>γ %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="Competitor SKU (log price)",
        yaxis_title="Focal SKU",
        title="Cross-price effects on mean log quantity",
        yaxis=dict(autorange="reversed"),
    )
    return _layout(fig, height=max(360, 28 * n + 80))


def optimization_bars(merged: pd.DataFrame, *, sku_col: str = "sku") -> go.Figure:
    skus = merged[sku_col].astype(str)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=("Price", "Expected revenue at optimal price"),
    )
    fig.add_trace(
        go.Bar(x=skus, y=merged["historical_avg_price"], name="Historical average"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=skus, y=merged["optimal_price"], name="Optimal"),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=skus, y=merged["mean_revenue"], name="Mean revenue", showlegend=False),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Revenue", row=2, col=1)
    fig.update_xaxes(title_text="SKU", row=2, col=1)
    fig.update_layout(barmode="group", title="Optimisation summary")
    return _layout(fig, height=560)
