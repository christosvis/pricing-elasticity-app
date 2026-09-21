import math

import streamlit as st

from utils.fitting import (
    MODEL_CLASSES,
    MODEL_HELP,
    build_model,
    build_panel_columns,
    build_sample_kwargs,
    fit_model,
    nutpie_available,
)
from utils.panel import default_control_columns, default_group_columns, group_candidate_columns, numeric_candidate_columns
from utils.state import clear_fit, require_panel

st.title("Fit demand model")
st.caption(
    "Sampling does **not** start when you change widgets. Press Fit after the spec is set. "
    "Default is **nutpie** NUTS (Rust), which is much faster than PyMC’s Python-mode NUTS on this Mac."
)

df = require_panel()

model_label = st.selectbox("Demand curve", list(MODEL_CLASSES.keys()))
st.caption(MODEL_HELP[model_label])

numeric_cols = numeric_candidate_columns(df)
group_cols = group_candidate_columns(df)
default_controls = [c for c in default_control_columns(df) if c in numeric_cols]
default_groups = [c for c in default_group_columns(df) if c in group_cols]

c1, c2 = st.columns(2)
with c1:
    control_columns = st.multiselect(
        "Control columns (shared across SKUs)",
        numeric_cols,
        default=default_controls,
    )
    quantity_floor = st.number_input(
        "Quantity floor (avoids log 0)",
        min_value=1e-6,
        value=1.0,
        format="%.4f",
    )
with c2:
    group_columns = st.multiselect(
        "Hierarchy columns (coarse → fine)",
        group_cols,
        default=default_groups,
        help="Partial pooling of intercepts and elasticities toward group means.",
    )
    region_col = None
    if "region" in df.columns:
        use_region = st.toggle("Use region in market cells", value=False)
        region_col = "region" if use_region else None

st.subheader("Cross-price elasticity")
cross_choice = st.segmented_control(
    "Cross-price mode",
    ["Off", "Within group", "All pairs"],
    default="Off",
    required=True,
)
cross_mode = None
cross_level = None
if cross_choice == "Within group":
    if not group_columns:
        st.warning("Within-group cross-price needs at least one hierarchy column.")
    else:
        cross_mode = "within_group"
        cross_level = st.selectbox(
            "Group level (0 = coarsest)",
            list(range(len(group_columns))),
            format_func=lambda i: f"{i}: {group_columns[i]}",
        )
    st.caption(
        "Requires a **balanced** panel: every period (and region, if used) must have one row per SKU."
    )
elif cross_choice == "All pairs":
    cross_mode = "all"
    st.caption("Estimates a directed effect for every SKU pair. Heavy with many SKUs.")

st.subheader("Sampler")
sampler_options = []
if nutpie_available():
    sampler_options.append("Nutpie NUTS (fast)")
sampler_options.append("PyMC NUTS (slow)")
sampler_label = st.segmented_control(
    "Engine",
    sampler_options,
    default=sampler_options[0],
    required=True,
    help="Nutpie is compiled NUTS. PyMC NUTS uses the Python PyTensor linker here (C compile fails on this Mac) and can take many minutes.",
)
sampler = "nutpie" if sampler_label.startswith("Nutpie") else "pymc"
if sampler == "pymc":
    st.warning(
        "PyMC NUTS is slow in this environment. Use nutpie unless you are debugging a sampler difference."
    )

s1, s2, s3, s4 = st.columns(4)
draws = s1.number_input("Draws", min_value=50, max_value=4000, value=200, step=50)
tune = s2.number_input("Tune", min_value=50, max_value=4000, value=200, step=50)
chains = s3.number_input("Chains", min_value=1, max_value=4, value=2)
seed = s4.number_input("Random seed", min_value=0, max_value=10_000, value=42)
target_accept = st.slider("Target accept", min_value=0.8, max_value=0.99, value=0.9, step=0.01)
st.caption(
    "Fewer draws/tune speeds exploration. Hierarchy and cross-price add parameters and slow sampling. "
    "A 6-SKU / 26-week demo with nutpie is typically under ~15 seconds."
)

with st.container(horizontal=True):
    fit_clicked = st.button("Fit model", type="primary", icon=":material/play_arrow:")
    if st.button("Clear fit", icon=":material/delete:"):
        clear_fit()
        st.rerun()

if fit_clicked:
    panel_columns = build_panel_columns(
        control_columns=control_columns,
        group_columns=group_columns,
        region_col=region_col,
        quantity_floor=float(quantity_floor),
    )
    try:
        model = build_model(
            model_label,
            panel_columns=panel_columns,
            cross_mode=cross_mode,
            cross_group_level=int(cross_level) if cross_level is not None else None,
        )
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    sample_kwargs = build_sample_kwargs(
        sampler=sampler,
        draws=int(draws),
        tune=int(tune),
        chains=int(chains),
        random_seed=int(seed),
        target_accept=float(target_accept),
    )
    with st.status("Sampling posterior…", expanded=True) as status:
        st.write(
            f"{model_label} · {sampler} · {int(draws)} draws × {int(chains)} chains · "
            f"{len(df):,} rows · {df['sku'].nunique()} SKUs"
        )
        try:
            fit_model(model, df, sample_kwargs)
            diagnostics = model.run_diagnostics()
        except Exception as exc:
            status.update(label="Fit failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Fit complete", state="complete")

    st.session_state.model = model
    st.session_state.diagnostics = diagnostics
    st.session_state.fit_meta = {
        "sampler": sampler,
        "model_label": model_label,
        "draws": int(draws),
        "tune": int(tune),
        "chains": int(chains),
        "seed": int(seed),
        "target_accept": float(target_accept),
        "controls": list(control_columns),
        "groups": list(group_columns),
        "cross": cross_choice,
    }
    st.session_state.eval_result = None
    st.session_state.opt_df = None
    st.success("Posterior is ready. Open Results, Optimize, or Evaluate.")

meta = st.session_state.get("fit_meta")
if meta:
    st.badge("Fitted", icon=":material/check_circle:", color="green")
    st.caption(
        f"{meta['model_label']} · {meta.get('sampler', 'pymc')} · {meta['draws']} draws / {meta['tune']} tune / "
        f"{meta['chains']} chains · cross-price: {meta['cross']}"
    )
    diag = st.session_state.get("diagnostics") or {}
    d1, d2 = st.columns(2)
    d1.metric("Divergent transitions", diag.get("n_divergent", "—"), border=True)
    max_rhat = diag.get("max_rhat")
    rhat_ok = isinstance(max_rhat, float) and math.isfinite(max_rhat)
    d2.metric(
        "Max R-hat",
        f"{max_rhat:.3f}" if rhat_ok else "—",
        border=True,
    )
    if rhat_ok and max_rhat > 1.05:
        st.warning("R-hat is above 1.05. Increase tune/draws or simplify the spec.")
    floor_skus = diag.get("floor_censored_skus") or {}
    if floor_skus:
        st.warning(
            "These SKUs sit at the quantity floor often, so own-price elasticity "
            f"is weakly identified: {floor_skus}"
        )
