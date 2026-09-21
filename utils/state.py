"""Session-state defaults. Fit results persist until data or spec changes."""

from __future__ import annotations

import streamlit as st

_DEFAULTS = {
    "panel_df": None,
    "data_source": None,
    "column_map": None,
    "model": None,
    "fit_meta": None,
    "diagnostics": None,
    "eval_result": None,
    "opt_df": None,
}


def init_state() -> None:
    for key, value in _DEFAULTS.items():
        st.session_state.setdefault(key, value)


def clear_fit() -> None:
    for key in ("model", "fit_meta", "diagnostics", "eval_result", "opt_df"):
        st.session_state[key] = None


def set_panel(df, *, source: str, column_map: dict | None = None) -> None:
    st.session_state.panel_df = df
    st.session_state.data_source = source
    st.session_state.column_map = column_map
    clear_fit()


def require_panel():
    df = st.session_state.get("panel_df")
    if df is None or df.empty:
        st.info("Load a demo panel or upload a CSV on the Data page first.")
        st.stop()
    return df


def require_model():
    model = st.session_state.get("model")
    if model is None:
        st.info("Fit a model on the Fit page first.")
        st.stop()
    return model
