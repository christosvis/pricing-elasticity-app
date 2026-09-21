# Pricing elasticity app

Streamlit app for [pypricing](https://github.com/arthurmello/pypricing): per-SKU demand curves, hierarchical pooling, optional cross-price effects, and revenue-optimal prices. 


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

