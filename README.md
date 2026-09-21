# Pricing elasticity app

Streamlit workbench for [pypricing](https://github.com/arthurmello/pypricing): per-SKU demand curves, hierarchical pooling, optional cross-price effects, and revenue-optimal prices. Walkthrough: [Arthur Mello, *pypricing: Bayesian Price Elasticity Estimation*](https://arthurmello.ai/blog/pypricing-bayesian-price-elasticity-estimation).

**Python 3.11 or 3.12 only.** `pymc-marketing` / `pydantic` currently fail on 3.13+ (including Streamlit Cloud’s 3.14 default).

No Snowflake: demo data or a CSV you upload.

## Streamlit Community Cloud

Python version is **not** taken from `runtime.txt`. You must set it in the UI ([docs](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python)):

1. Delete the existing app (Python cannot be changed in place).
2. Redeploy from [christosvis/pricing-elasticity-app](https://github.com/christosvis/pricing-elasticity-app), entrypoint `streamlit_app.py`.
3. Open **Advanced settings** → **Python version** → **3.12**.
4. Deploy.

If logs still show `/home/adminuser/venv/lib/python3.14/`, the app is still on 3.14 — delete and redeploy with 3.12 selected.

MCMC is heavy for the free Cloud CPU. Keep demo SKUs/periods small and use **Nutpie NUTS**.

## Local setup

```bash
python3.12 -m venv .venv   # or python3.11
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

If PyTensor C compilation fails on macOS (`library 'd64' not found`):

```bash
export PYTENSOR_FLAGS=cxx=
```

The app also sets this automatically.

## Pages

| Page | What it does |
| --- | --- |
| **Data** | Load `generate_mock_data` or upload a CSV (map sku / price / quantity) |
| **Fit** | Log-log, quadratic, or sigmoid; optional hierarchy and cross-price. Default sampler is **nutpie** NUTS (Fit button only). |
| **Results** | Elasticity posteriors, response / revenue curves, posterior predictive check |
| **Optimize** | Independent per-SKU revenue search inside price bounds |
| **Evaluate** | Last-period holdout RMSE and HDI coverage (does not overwrite the main fit) |

## Panel schema

Required: `sku`, `price` (> 0), `quantity` (≥ 0). Optional: `period` (holdout), `region` (cross-price cells), `control_*`, category columns for partial pooling.

Zero quantities are floored at 1.0 inside the log-demand likelihood (pypricing default).
