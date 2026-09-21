import pandas as pd
import streamlit as st

from utils.charts import calibration_scatter
from utils.fitting import build_model, build_sample_kwargs
from utils.state import require_panel

st.title("Time-aware holdout")
st.caption(
    "Holds out the **last** fraction of unique periods (never a random split). "
    "This fits a **copy** of the spec so it does not overwrite the main Fit posterior."
)

df = require_panel()
if "period" not in df.columns:
    st.warning("The panel needs a `period` column for a time-aware split. Map it on the Data page.")
    st.stop()

n_periods = int(df["period"].nunique())
st.metric("Unique periods", f"{n_periods:,}", border=True)
if n_periods < 4:
    st.warning("Need at least a handful of periods for a useful holdout.")

meta = st.session_state.get("fit_meta")
if meta is None:
    st.info("Set and fit a spec on the Fit page first so Evaluate can copy it.")
    st.stop()

test_size = st.slider("Test fraction (last periods)", min_value=0.1, max_value=0.4, value=0.2, step=0.05)
hdi_prob = st.slider("HDI probability", min_value=0.5, max_value=0.99, value=0.9, step=0.01)

if st.button("Run holdout", type="primary", icon=":material/fact_check:"):
    model = st.session_state.model
    eval_model = build_model(
        meta["model_label"],
        panel_columns=model.panel_columns,
        cross_mode=(
            None
            if meta["cross"] == "Off"
            else "within_group"
            if meta["cross"] == "Within group"
            else "all"
        ),
        cross_group_level=(
            model.cross_elasticity.group_level if model.cross_elasticity is not None else None
        ),
    )
    sample_kwargs = build_sample_kwargs(
        sampler=meta.get("sampler", "pymc"),
        draws=meta["draws"],
        tune=meta["tune"],
        chains=meta["chains"],
        random_seed=meta["seed"],
        target_accept=float(meta.get("target_accept", 0.9)),
    )
    with st.status("Fitting on the early periods…", expanded=True) as status:
        try:
            out = eval_model.fit_train_test(
                df,
                test_size=float(test_size),
                period_col="period",
                hdi_prob=float(hdi_prob),
                **sample_kwargs,
            )
        except Exception as exc:
            status.update(label="Holdout failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Holdout complete", state="complete")
    st.session_state.eval_result = out

out = st.session_state.get("eval_result")
if out is None:
    st.stop()

with st.container(horizontal=True):
    st.metric("Test RMSE (quantity)", f"{out['rmse']:.2f}", border=True)
    st.metric("HDI coverage", f"{out['hdi_coverage']:.0%}", border=True)
    st.metric("Train rows", f"{out['n_train']:,}", border=True)
    st.metric("Test rows", f"{out['n_test']:,}", border=True)

st.caption(
    "Coverage is the share of true test quantities inside the predicted HDI. "
    "Far below the nominal HDI probability means intervals are too tight."
)

preds: pd.DataFrame = out["test_predictions"]
st.plotly_chart(calibration_scatter(preds, "quantity"))
st.dataframe(preds.head(100), hide_index=True)
