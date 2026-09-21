import numpy as np
import streamlit as st

from utils.charts import (
    calibration_scatter,
    cross_price_heatmap,
    elasticity_forest,
    local_elasticity_curve,
    multiplier_forest,
    ppc_series,
    response_curve,
    revenue_curve,
)
from utils.fitting import controls_for_sku
from utils.state import require_model, require_panel

st.title("Posterior results")

df = require_panel()
model = require_model()
meta = st.session_state.get("fit_meta") or {}
hdi_prob = st.slider("HDI probability", min_value=0.5, max_value=0.99, value=0.9, step=0.01)

st.subheader("Own-price elasticity")
st.caption(
    "A value of −1.5 means a 1% price increase is associated with about a 1.5% drop "
    "in quantity, in expectation. The dashed line is unit elasticity (−1)."
)
st.plotly_chart(elasticity_forest(model, hdi_prob=hdi_prob))

summary = model.fit_summary()
st.dataframe(summary.reset_index().rename(columns={"index": "parameter"}))

if meta.get("model_label", "").startswith("Log-log"):
    st.subheader("Quantity multiplier vs a price change")
    pct = st.slider("Price change (%)", min_value=-40, max_value=40, value=10, step=1)
    if pct == 0:
        st.info("Pick a non-zero price change.")
    else:
        mult = 1.0 + pct / 100.0
        qty = model.quantity_multiplier_summary(price_multiplier=mult, hdi_prob=hdi_prob)
        st.plotly_chart(multiplier_forest(qty, pct=int(pct), hdi_prob=hdi_prob))
        st.dataframe(qty.reset_index() if hasattr(qty, "reset_index") else qty)
        st.caption(
            f"Posterior of quantity × {mult:.2f}^elasticity for a {pct:+d}% price move. "
            "Only valid for constant-elasticity (log-log) models."
        )

st.subheader("Demand and revenue curves")
skus = list(model.sku_levels_)
sku = st.selectbox("SKU", skus)
sku_hist = df.loc[df[model.sku_col] == sku, model.price_col]
low = float(sku_hist.min() * 0.7)
high = float(sku_hist.max() * 1.3)
n_grid = st.slider("Price grid points", min_value=15, max_value=60, value=30)
price_grid = np.linspace(low, high, int(n_grid))
try:
    controls = controls_for_sku(df, model, sku)
except Exception as exc:
    st.error(str(exc))
    st.stop()

curve_view = st.segmented_control(
    "Curve",
    ["Response", "Revenue", "Local elasticity"],
    default="Response",
    required=True,
)
if curve_view == "Response":
    st.plotly_chart(
        response_curve(
            model, sku=sku, price_grid=price_grid, controls=controls, hdi_prob=hdi_prob
        )
    )
elif curve_view == "Revenue":
    st.plotly_chart(
        revenue_curve(
            model, sku=sku, price_grid=price_grid, controls=controls, hdi_prob=hdi_prob
        )
    )
else:
    st.plotly_chart(
        local_elasticity_curve(
            model, sku=sku, price_grid=price_grid, controls=controls, hdi_prob=hdi_prob
        )
    )

st.subheader("Posterior predictive check")
cal_style = st.segmented_control("View", ["Scatter", "Time series"], default="Scatter", required=True)
preds = model.predict(df, hdi_prob=hdi_prob, random_seed=0)
if cal_style == "Scatter":
    st.plotly_chart(calibration_scatter(preds, model.quantity_col))
else:
    st.plotly_chart(ppc_series(preds, model, hdi_prob=hdi_prob))

if model.cross_elasticity is not None:
    st.subheader("Cross-price effects")
    st.plotly_chart(cross_price_heatmap(model, agg="mean"))
    st.caption("Diagonal is own-price (in elasticity_sku). Masked cells were not estimated.")
