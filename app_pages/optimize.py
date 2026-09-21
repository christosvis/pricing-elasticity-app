import warnings

import pandas as pd
import streamlit as st

from utils.charts import optimization_bars
from utils.fitting import controls_df_for_opt
from utils.state import require_model, require_panel

st.title("Revenue-optimal prices")
st.caption(
    "Per-SKU search that maximises posterior **mean** revenue inside the bounds you set. "
    "Independent across SKUs — not a joint market optimisation. Unavailable when cross-price is on."
)

df = require_panel()
model = require_model()

if model.cross_elasticity is not None:
    st.warning(
        "This fit includes cross-price terms, so revenue for one SKU depends on the rest of the cell. "
        "Use counterfactual `predict()` on a full price scenario instead of this page."
    )
    st.stop()

low_mult = st.slider("Lower bound vs historical min", min_value=0.5, max_value=1.0, value=0.8, step=0.05)
high_mult = st.slider("Upper bound vs historical max", min_value=1.0, max_value=2.0, value=1.3, step=0.05)

price_bounds = {
    sku: (
        float(g[model.price_col].min() * low_mult),
        float(g[model.price_col].max() * high_mult),
    )
    for sku, g in df.groupby(model.sku_col)
}

hist = (
    df.groupby(model.sku_col)[model.price_col]
    .mean()
    .rename("historical_avg_price")
    .reset_index()
)
st.dataframe(
    pd.DataFrame(
        [
            {
                "sku": sku,
                "bound_low": lo,
                "bound_high": hi,
            }
            for sku, (lo, hi) in price_bounds.items()
        ]
    )
)

if st.button("Optimize prices", type="primary", icon=":material/payments:"):
    controls_df = controls_df_for_opt(df, model)
    with st.spinner("Searching per SKU…"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            opt = model.optimize_prices(price_bounds=price_bounds, controls_df=controls_df)
            notes = [str(w.message) for w in caught]
    st.session_state.opt_df = opt.reset_index()
    st.session_state.opt_notes = notes
    st.session_state.opt_controls = controls_df

opt = st.session_state.get("opt_df")
if opt is None:
    st.stop()

for note in st.session_state.get("opt_notes") or []:
    st.info(note)

merged = opt.merge(hist, left_on="sku", right_on=model.sku_col, how="left")
st.dataframe(merged)

n_bound = int((merged["at_bound"].notna()).sum()) if "at_bound" in merged.columns else 0
st.metric(
    "SKUs at a bound",
    f"{n_bound} / {len(merged)}",
    border=True,
)
st.caption(
    "For log-log demand, expected revenue scales like price^(1 + elasticity). "
    "If |elasticity| ≠ 1 the optimum is usually the bound you supplied — that is the math, not a search bug."
)

st.plotly_chart(optimization_bars(merged, sku_col=model.sku_col))

st.download_button(
    "Download optimal prices",
    data=merged.to_csv(index=False).encode("utf-8"),
    file_name="optimal_prices.csv",
    mime="text/csv",
    icon=":material/download:",
)
