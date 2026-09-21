import matplotlib

matplotlib.use("Agg")

import os
from pathlib import Path

import streamlit as st

from utils.state import init_state

_ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_ROOT / ".mplconfig"))
os.environ.setdefault("PYTENSOR_FLAGS", "cxx=")
(_ROOT / ".mplconfig").mkdir(exist_ok=True)

st.set_page_config(
    page_title="Pypricing",
    page_icon=":material/sell:",
    layout="wide",
)

init_state()

page = st.navigation(
    [
        st.Page("app_pages/data.py", title="Data", icon=":material/table_chart:"),
        st.Page("app_pages/fit.py", title="Fit", icon=":material/tune:"),
        st.Page("app_pages/results.py", title="Results", icon=":material/analytics:"),
        st.Page("app_pages/optimize.py", title="Optimize", icon=":material/payments:"),
        st.Page("app_pages/evaluate.py", title="Evaluate", icon=":material/fact_check:"),
    ],
    position="top",
)
st.caption("Made by Christos Visvardis · [visvardis.com](https://visvardis.com/)")
page.run()
