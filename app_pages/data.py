import streamlit as st

from utils.panel import (
    canonicalize_panel,
    generate_demo_panel,
    guess_column,
    panel_summary,
)
from utils.state import set_panel

st.title("Price panel")
st.caption(
    "Long-format data: one row per SKU–period. Required columns are "
    "**sku**, **price** (strictly positive), and **quantity** (non-negative). "
    "Optional `control_*`, category, and `period` columns are used on later pages."
)

source = st.segmented_control(
    "Source",
    ["Demo dataset", "Upload CSV"],
    default="Demo dataset",
    key="data_source_choice",
    required=True,
)

if source == "Demo dataset":
    st.markdown(
        "Synthetic panel from [`pypricing.generate_mock_data`](https://arthurmello.ai/blog/pypricing-bayesian-price-elasticity-estimation). "
        "Uses weekly periods, per-SKU prices, and optional category / control columns."
    )
    with st.form("demo_form"):
        c1, c2, c3 = st.columns(3)
        n_periods = c1.number_input("Periods (weeks)", min_value=8, max_value=104, value=26)
        n_skus = c2.number_input("SKUs", min_value=2, max_value=20, value=6)
        n_controls = c3.number_input("Control columns", min_value=0, max_value=4, value=1)
        c4, c5, c6 = st.columns(3)
        n_categories = c4.number_input(
            "Top-level categories",
            min_value=2,
            max_value=6,
            value=2,
            help="Creates a category_1 column for hierarchical pooling.",
        )
        shape = c5.selectbox(
            "Demand shape in the DGP",
            ["log_log", "quadratic", "sigmoid"],
            index=0,
        )
        seed = c6.number_input("Random seed", min_value=0, max_value=10_000, value=0)
        seasonality = st.toggle("Include seasonality", value=True)
        submitted = st.form_submit_button("Load demo", type="primary", icon=":material/science:")

    if submitted:
        with st.spinner("Generating mock panel…"):
            df = generate_demo_panel(
                n_periods=int(n_periods),
                n_skus=int(n_skus),
                n_controls=int(n_controls),
                n_categories=int(n_categories),
                shape=shape,
                random_state=int(seed),
                include_seasonality=bool(seasonality),
            )
        set_panel(df, source="demo")
        st.success(f"Loaded {len(df):,} rows across {df['sku'].nunique()} SKUs.")

else:
    st.markdown(
        "Upload a CSV with at least sku, price, and quantity. Map columns if names differ. "
        "Zeros in quantity are allowed; the model floors them at 1.0 before taking logs."
    )
    uploaded = st.file_uploader("CSV file", type=["csv"], key="csv_upload")
    if uploaded is not None:
        raw = st.session_state.get("_raw_upload")
        if st.session_state.get("_raw_upload_name") != uploaded.name:
            raw = None
        if raw is None:
            import pandas as pd

            raw = pd.read_csv(uploaded)
            st.session_state._raw_upload = raw
            st.session_state._raw_upload_name = uploaded.name
        cols = list(raw.columns)
        with st.form("map_form"):
            st.subheader("Column mapping")
            m1, m2, m3 = st.columns(3)
            sku_col = m1.selectbox(
                "SKU",
                cols,
                index=cols.index(guess_column(cols, "sku")) if guess_column(cols, "sku") in cols else 0,
            )
            price_col = m2.selectbox(
                "Price",
                cols,
                index=cols.index(guess_column(cols, "price")) if guess_column(cols, "price") in cols else 0,
            )
            qty_col = m3.selectbox(
                "Quantity",
                cols,
                index=cols.index(guess_column(cols, "quantity")) if guess_column(cols, "quantity") in cols else 0,
            )
            m4, m5 = st.columns(2)
            period_guess = guess_column(cols, "period")
            period_options = ["(none)"] + cols
            period_col = m4.selectbox(
                "Period (optional, needed for holdout)",
                period_options,
                index=period_options.index(period_guess) if period_guess else 0,
            )
            region_guess = guess_column(cols, "region")
            region_col = m5.selectbox(
                "Region (optional, for cross-price cells)",
                period_options,
                index=period_options.index(region_guess) if region_guess else 0,
            )
            mapped = st.form_submit_button(
                "Use this file", type="primary", icon=":material/upload:"
            )

        if mapped:
            mapping = {
                "sku": sku_col,
                "price": price_col,
                "quantity": qty_col,
                "period": None if period_col == "(none)" else period_col,
                "region": None if region_col == "(none)" else region_col,
            }
            try:
                panel = canonicalize_panel(raw, mapping)
            except Exception as exc:
                st.error(str(exc))
            else:
                set_panel(panel, source="upload", column_map=mapping)
                st.success(f"Loaded {len(panel):,} rows from {uploaded.name}.")

df = st.session_state.get("panel_df")
if df is None:
    st.stop()

stats = panel_summary(df)
with st.container(horizontal=True):
    st.metric("Rows", f"{stats['rows']:,}", border=True)
    st.metric("SKUs", f"{stats['skus']:,}", border=True)
    st.metric(
        "Price range",
        f"{stats['price_min']:.2f} – {stats['price_max']:.2f}"
        if stats["price_min"] is not None
        else "—",
        border=True,
    )
    st.metric(
        "Periods",
        f"{stats['periods']:,}" if stats["periods"] is not None else "—",
        border=True,
    )

if stats["nonpositive_price"]:
    st.error(
        f"{stats['nonpositive_price']} row(s) have non-positive price. "
        "pypricing requires strictly positive prices."
    )
if stats["zero_qty_share"] > 0:
    st.caption(
        f"{stats['zero_qty_share']:.0%} of rows have quantity ≤ 0. "
        "Those observations are floored at 1.0 inside the log-demand likelihood."
    )

st.subheader("Preview")
st.dataframe(df.head(50), hide_index=True)
st.download_button(
    "Download panel CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="price_panel.csv",
    mime="text/csv",
    icon=":material/download:",
)

with st.expander("Expected schema"):
    st.markdown(
        """
        | Column | Required | Notes |
        | --- | --- | --- |
        | `sku` | yes | Product identifier |
        | `price` | yes | Strictly positive |
        | `quantity` | yes | Non-negative |
        | `period` | for holdout / cross-price | Time index; last periods are held out in Evaluate |
        | `region` | optional | Market cell with `period` for cross-price |
        | `control_*` | optional | Shared numeric regressors |
        | category columns | optional | Hierarchy / partial pooling |
        """
    )
