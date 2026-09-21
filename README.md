# Pypricing — Bayesian price elasticity (Streamlit)

Local workbench for [pypricing](https://github.com/arthurmello/pypricing): per-SKU demand curves, hierarchical pooling, optional cross-price effects, and revenue-optimal prices. Walkthrough: [Arthur Mello, *pypricing: Bayesian Price Elasticity Estimation*](https://arthurmello.ai/blog/pypricing-bayesian-price-elasticity-estimation).

This folder uses its **own virtualenv**. Do not add `pypricing` / PyMC-Marketing to marketing-ax Poetry (that stack is PyMC 5; pypricing pulls `pymc-marketing>=0.19`).

No Snowflake: demo data or a CSV you upload.

## Setup

Python **3.11 or 3.12**. From this folder:

```bash
cd christos-analyses/pypricing
python3.11 -m venv pypricing-venv   # 3.12 also fine if installed
source pypricing-venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source pypricing-venv/bin/activate
# If PyTensor C compilation fails on macOS (`library 'd64' not found`), keep:
export PYTENSOR_FLAGS=cxx=
streamlit run streamlit_app.py --server.port 8502
```

## Pages

| Page | What it does |
| --- | --- |
| **Data** | Load `generate_mock_data` or upload a CSV (map sku / price / quantity) |
| **Fit** | Choose log-log, quadratic, or sigmoid; optional hierarchy and cross-price. Default sampler is **nutpie** NUTS (Fit button only). |
| **Results** | Elasticity posteriors, response / revenue curves, posterior predictive check |
| **Optimize** | Independent per-SKU revenue search inside price bounds |
| **Evaluate** | Last-period holdout RMSE and HDI coverage (does not overwrite the main fit) |

## Panel schema

Required: `sku`, `price` (> 0), `quantity` (≥ 0). Optional: `period` (holdout), `region` (cross-price cells), `control_*`, category columns for partial pooling.

Zero quantities are floored at 1.0 inside the log-demand likelihood (pypricing default).

## Speed

PyTensor C compilation fails on this Mac (`library 'd64' not found`), so the app sets `PYTENSOR_FLAGS=cxx=` and does **not** use PyMC’s compiled NUTS. Fits go through **nutpie** instead (Rust NUTS). A 6-SKU / 26-week hierarchical demo is ~10 seconds at 200 draws × 2 chains. Switch to “PyMC NUTS” only to compare samplers — that path can take many minutes. Hierarchy and cross-price add parameters; turn them off while exploring.

## Layout

```
pypricing/
├── pypricing-venv/     # isolated env (gitignored)
├── streamlit_app.py
├── app_pages/
├── utils/
├── requirements.txt
└── README.md
```
