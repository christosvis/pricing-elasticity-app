# christos-analyses — conventions

Personal analysis workspace under `marketing-ax`. Use this doc (and point Cursor to it) when starting or continuing any project in this folder.

Repo-wide context: [`ai_agent_docs/README.md`](../ai_agent_docs/README.md) (metrics, SQL style, data landscape).

---

## Snowflake connection (default for every analysis)

| Setting | Value |
|---------|--------|
| **User** | `christos.visvardis@external.wolt.com` |
| **Account** | `ig78751.eu-west-1` (locator — **not** your email) |
| **Database / schema** | `PRODUCTION.PUBLIC` (or `production` / `public` in SQLAlchemy) |
| **Warehouse** | `EXPLORATION_L` (use `EXPLORATION_3XL` only for heavy jobs) |
| **Role** | `ANALYTICS_DEV` |
| **Auth** | `externalbrowser` (SSO in browser) |

### Notebook boilerplate (standard for all Snowflake analyses)

**Reference:** [`uac-budget-shift/uac_budget_shift.ipynb`](uac-budget-shift/uac_budget_shift.ipynb) — copy this pattern for new work and when upgrading older notebooks.

Use **`snowflake.connector`** (not SQLAlchemy) and pull **all** `sql/` files in **one connection** — one browser SSO login per Run All. Do **not** call `create_engine()` or `connect()` in multiple cells; without `keyring`, each new connection can open Chrome again.

#### 1. Setup cell — flag + SQL file list

```python
from pathlib import Path
import os

WAREHOUSE = "EXPLORATION_L"
SNOWFLAKE_ROLE = "ANALYTICS_DEV"

# True: re-pull all sql/ → data/ or outputs/*.csv on Run All (one SSO login).
# False: read cached CSVs only (fast chart reruns, no browser).
REFRESH_FROM_SNOWFLAKE = True

if not os.environ.get("SNOWFLAKE_USER"):
    os.environ["SNOWFLAKE_USER"] = "christos.visvardis@external.wolt.com"


def project_dir() -> Path:
    """Resolve christos-analyses/<project-name> from repo or subfolder cwd."""
    p = Path.cwd().resolve()
    if p.name == "my-project":
        return p
    for d in [p, *p.parents]:
        hit = d / "christos-analyses" / "my-project"
        if hit.is_dir():
            return hit
    raise FileNotFoundError("Could not locate christos-analyses/<project>")


PROJECT_DIR = project_dir()
DATA_DIR = PROJECT_DIR / "data"       # or outputs/ — pick one per project, stay consistent
SQL_DIR = PROJECT_DIR / "sql"
DATA_DIR.mkdir(parents=True, exist_ok=True)

REFRESH_SQL_FILES = [
    "01_my_query.sql",
    "02_other_query.sql",
    # one entry per file in sql/ that feeds the notebook
]
```

#### 2. Snowflake refresh cell — run once, before analysis cells

```python
import pandas as pd
import snowflake.connector

if REFRESH_FROM_SNOWFLAKE:
    print("Connecting to Snowflake (one browser login)...")
    conn = snowflake.connector.connect(
        account="ig78751.eu-west-1",
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="externalbrowser",
        warehouse=WAREHOUSE,
        role=SNOWFLAKE_ROLE,
        database="production",
        schema="public",
    )
    try:
        for name in REFRESH_SQL_FILES:
            path = SQL_DIR / name
            df = pd.read_sql(path.read_text(), conn)
            df.columns = df.columns.str.lower()  # Snowflake returns UPPERCASE
            out = DATA_DIR / f"{path.stem}.csv"
            df.to_csv(out, index=False)
            print(f"  {out.name}: {len(df):,} rows")
    finally:
        conn.close()
    print("Snowflake refresh done.")
else:
    print("Skipping Snowflake refresh — reading cached CSVs")
```

#### 3. Analysis cells — always read CSVs (never Snowflake here)

```python
df = pd.read_csv(DATA_DIR / "01_my_query.csv")
df.columns = df.columns.str.lower()
df["event_date"] = pd.to_datetime(df["event_date"])  # lowercase before parse_dates
```

**Rules**

| Rule | Why |
|------|-----|
| One `connect()` in the refresh cell only | Avoids repeated Chrome SSO popups |
| `df.columns.str.lower()` before `to_csv` | Snowflake returns `SPEND_DATE`; pandas expects `spend_date` |
| Lowercase columns before `parse_dates` / column access | Prevents `ValueError: Missing column` on refresh |
| SQL stays in `sql/` | Reproducible, diffable, runnable in Snowsight |
| Optional `scripts/refresh_*.py` | Same single-connection pattern for terminal-only refresh |

Install token caching so re-runs within a session skip SSO:

```bash
pip install 'snowflake-connector-python[secure-local-storage]'
```

### Refresh flag (summary)

```python
REFRESH_FROM_SNOWFLAKE = True   # Run All → latest data (one SSO login)
REFRESH_FROM_SNOWFLAKE = False  # Run All → cached data/ or outputs/*.csv only
```

| Goal | Setting |
|------|---------|
| **Latest data + full analysis** | `True`, then Run All |
| **Tweak charts on existing pull** | `False`, then Run All |
| **Refresh without notebook** | `python scripts/refresh_*.py` in the project folder |

Keep **SQL in `sql/`** as the source of truth; notebooks read CSVs so reruns are fast and diffable.

### Legacy notebooks

These still use the older SQLAlchemy `get_snowflake_engine()` pattern — migrate to the boilerplate above when you touch them:

| Project | Status |
|---------|--------|
| [`uac-budget-shift/`](uac-budget-shift/) | **Standard** (`snowflake.connector`, single refresh cell) |
| [`sem-web-app/`](sem-web-app/) | Legacy SQLAlchemy |
| [`affiliate-ctv/`](affiliate-ctv/) | Legacy SQLAlchemy |
| [`market_similarity/`](market_similarity/) | Legacy SQLAlchemy |

### Shell / scripts

```bash
# Only if you use CLI scripts that read env vars:
export SNOWFLAKE_USER="christos.visvardis@external.wolt.com"
export SNOWFLAKE_ACCOUNT="ig78751.eu-west-1"   # never set this to your email

# If you see 404 on christos.visvardis@external.wolt.com.snowflakecomputing.com:
unset SNOWFLAKE_ACCOUNT
```

Optional per-project `.env` (gitignored): see `market_similarity/.env.example`.

### Common mistake

`SNOWFLAKE_ACCOUNT` must be `ig78751.eu-west-1`. If you set it to your email, SSO hits a non-existent host and returns **404**.

---

## Folder layout (per analysis)

```
christos-analyses/<project-name>/
├── README.md or analysis_spec.md   # question, decisions, filters (required for non-trivial work)
├── findings_summary.md             # optional: stakeholder-ready takeaways
├── <project>.ipynb                 # main notebook
├── sql/                            # reproducible queries (lowercase SQL)
├── data/                           # pulled CSVs (Snowflake exports + public seeds)
├── outputs/                        # charts, tables, intermediate exports
└── scripts/                        # optional: export_*.py, sanity checks
```

**Do not commit:** `.venv/`, `<project>-venv/`, `.env`, large raw dumps unless the team agrees.

### Isolated project venvs

When a project needs its own environment (heavy or conflicting deps: Meridian, PyMC-Marketing, DoubleML, …), **do not** name it `.venv` — that collides with marketing-ax’s root env.

Name it **`<short-project>-venv`** in the project folder (e.g. `doubleml-venv`, `meridian-pymc-venv`). Gitignore that directory. Register a Jupyter kernel with the same name.

---

## Visualization (Plotly)

**Prefer [Plotly](https://plotly.com/python/)** (`plotly.express`, `plotly.graph_objects`) for notebook charts — interactive hover, zoom, and legend toggles. Avoid matplotlib for new work unless you need a one-off static export with no extra dependencies.

- **In notebooks:** `fig.show()` (renderer: `notebook_connected` in Jupyter / VS Code).
- **Optional PNGs:** `fig.write_image(...)` via [Kaleido](https://github.com/plotly/Kaleido) — see `show_fig()` in `sem-web-app/sem_web_app_analysis.ipynb`.
- **Dependencies:** `plotly` and `kaleido` are in the repo root `pyproject.toml`.

Reference implementation: [`sem-web-app/sem_web_app_analysis.ipynb`](sem-web-app/sem_web_app_analysis.ipynb).

---

## SQL rules (short)

Follow [`ai_agent_docs/06_sql_conventions.md`](../ai_agent_docs/06_sql_conventions.md):

- Lowercase keywords; `where 1=1` then `and ...`
- Fully qualify: `production.intermediate.f_purchases`, `production.marketing.consumer_install_attribution_with_incrementality`, etc.
- Purchases: `is_consumer_core` and `status in ('delivered', 'refunded')` unless the spec says otherwise
- Prefer `group by all` where appropriate
- Test on one country / short date range before full pulls

Document locked filters in `analysis_spec.md` (cohort definition, exclusions, date window).

---

## Data & terminology

| Topic | Convention |
|-------|------------|
| **Country codes** | ISO-3 (`FIN`, `DEU`, `ROU`). Map `ROM` → `ROU` when needed. |
| **FTU** | First-time user / first purchase cohort — not “new user” in prose. |
| **28-day vs calendar month** | Marketing AX often uses **28-day periods**; marketing/CCR reports often use **calendar months**. Label both when comparing. |
| **Paid Online** | `install_origin_group = 'Paid → Online'` (matches many Looker UA views). |
| **Public / external data** | Population, PPP — keep in `data/seed/` with source note; do not pretend they live in Snowflake. |
| **Internal marketing metrics** | Often `consumer.mkt_gd_combined_metrics` (daily `period = 'day'` to avoid double-count). |

Key tables: [`ai_agent_docs/03_data_landscape.md`](../ai_agent_docs/03_data_landscape.md).

---

## Analysis workflow

1. **Spec first** — `analysis_spec.md`: question, decisions, tables, filters, outputs.
2. **SQL in `sql/`** — run in Snowsight or via the notebook refresh cell (`REFRESH_FROM_SNOWFLAKE = True`).
3. **Sanity-check** — row counts, one known market, overlap vs prior CSV if refreshing.
4. **Notebook** — refresh cell writes `data/` or `outputs/`; analysis cells load CSVs; **Plotly** charts to `outputs/`.
5. **Findings** — `findings_summary.md` when sharing outside the notebook.

**Run All with latest data:** set `REFRESH_FROM_SNOWFLAKE = True` in §1 → one SSO login → all `sql/` exported → analysis runs on fresh CSVs.

Before claiming results are final: actually run the query and inspect aggregates (not just “SQL looks fine”).

---

## Projects in this folder

| Project | Purpose |
|---------|---------|
| [`sem-web-app/`](sem-web-app/) | Paid Online FTUs — first-purchase platform, M2, SEM-only Looker filters |
| [`uac-budget-shift/`](uac-budget-shift/) | UAC budget reallocation — spend timeline + overall cohort performance |
| [`affiliate-ctv/`](affiliate-ctv/) | Affiliate CTV blackout test — market screening (monthly spend only) |
| [`swe-ooh-test-sep-2026/`](swe-ooh-test-sep-2026/) | Sweden Stockholm OOH Sep 2026 — geo design + [post-campaign FTU ATT notebook](swe-ooh-test-sep-2026/swe_ooh_post_campaign_ftu.ipynb); [marketing readout](swe-ooh-test-sep-2026/marketing_readout.md) |
| [`tiktok-geo-test-sep-2026/`](tiktok-geo-test-sep-2026/) | Nordics TikTok UA geo-lift (FIN/NOR/SWE, Aug–Sep 2026) — city FTU GeoLift readout |
| [`meridian-pymc-comparison/`](meridian-pymc-comparison/) | Synthetic MMM parameter recovery — Meridian vs PyMC-Marketing on shared ground-truth data |
| [`mmm-budget-optimizer/curve-budget-optimizer/`](mmm-budget-optimizer/curve-budget-optimizer/) | Curve-only UA budget optimizer (Streamlit) — reads `MMM_SATURATION_POINTS`, no live `.nc` |
| [`pymc-mmm/`](pymc-mmm/) | Streamlit workbench for live PyMC-Marketing MMM (isolated venv; Phase 2 families, YAML, scenarios, budget) |
| [`meridian-app/`](meridian-app/) | Meridian MMM app (Streamlit; isolated `meridian-venv`, JAX; geo R&F samples, ROI/mROI, BudgetOptimizer) |
| [`meridian-mmm/`](meridian-mmm/) | Google Meridian Full-Funnel Colab locally (isolated `meridian-venv`; `google-meridian[colab,scenarioplanner,schema]`) |
| [`meridian-geox/`](meridian-geox/) | Google Meridian GeoX sandbox — geo incrementality design/analysis (isolated `geox-venv`; PyPI `meridian-geox`) |
| [`meridian-geox-app/`](meridian-geox-app/) | Streamlit GeoX workbench (`geox-app-venv`) — design/analysis, quality checks, cooldown, Meridian prior export |
| [`doubleml-pipeline/`](doubleml-pipeline/) | Google DoubleML Pipeline sandbox — DML for incremental marketing (synthetic geo-week panel; isolated venv) |
| [`pypricing/`](pypricing/) | Streamlit Bayesian price elasticity workbench (`pypricing-venv`; demo panel + CSV; pypricing / PyMC — not root Poetry) |

When adding a new project, copy the Snowflake refresh pattern from [`uac-budget-shift/uac_budget_shift.ipynb`](uac-budget-shift/uac_budget_shift.ipynb) and link it here.

---

## Snowflake MCP vs notebook pulls

Use **both** — they solve different problems. Do not replace the notebook + CSV workflow with MCP-only.

| Channel | Best for | How |
|---------|----------|-----|
| **Notebook** (`REFRESH_FROM_SNOWFLAKE`, `sql/` → `data/`) | Official pulls, Plotly pipelines, Run All with latest data | `snowflake.connector`, one connection in refresh cell; warehouse `EXPLORATION_L` |
| **Cursor + Snowflake MCP** | Exploring data, drafting/reviewing `sql/`, ad-hoc questions, semantic-layer-guided SQL | Enabled globally in Cursor (**Tools & MCP** → `snowflake-analytics`); bootstrap rule in [`semantic-layer.mdc`](../.cursor/rules/semantic-layer.mdc) |

**Hybrid workflow**

1. **Explore / draft** in Cursor (MCP loads `PRODUCTION._PRETZEL.SEMANTIC_MODELS` when relevant).
2. **Lock** the query in `sql/` and sanity-check (row counts, one market, date range).
3. **Refresh** — set `REFRESH_FROM_SNOWFLAKE = True` and Run All, or `python scripts/refresh_*.py` → write `data/*.csv` or `outputs/*.csv`.
4. **Iterate charts** — set `REFRESH_FROM_SNOWFLAKE = False` and Run All (no browser, uses cached CSVs).

**Notes**

- Jupyter cannot call Cursor MCP — notebooks use the `snowflake.connector` refresh cell above (or Snowsight + manual CSV).
- MCP setup may default to warehouse `exploration_m`; keep notebook pulls on `EXPLORATION_L` unless you intentionally change both.
- Finished analyses should still ship `sql/`, cached `data/`, and `outputs/` — not “live MCP only.”

---

## Cursor / agent

A workspace rule applies automatically when you open or edit files under `christos-analyses/`:

- **Rule:** [`.cursor/rules/christos-analyses.mdc`](../.cursor/rules/christos-analyses.mdc)
- **Default:** read **this README** at the start of every task in this folder.
- **Semantic layer:** repo-wide [`semantic-layer.mdc`](../.cursor/rules/semantic-layer.mdc) — agents load bootstrap from Snowflake before analytical queries; notebooks are unchanged.

Agents should:

- Use the Snowflake settings in this file (user + `ig78751.eu-west-1`).
- Use **MCP** for exploration and SQL drafting; use **`REFRESH_FROM_SNOWFLAKE` + `sql/`** + single `snowflake.connector` refresh cell for committed pulls.
- Respect Wolt terminology from `ai_agent_docs/01_metrics_definitions.md`.
- Not commit secrets, `.env`, or notebook `.venv` trees.

Shorter Snowflake-only reminder: [`SNOWFLAKE.md`](SNOWFLAKE.md) (points here).
