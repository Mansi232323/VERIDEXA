# 🧠 VERIDEXA — Intelligent Data Analyst Suite

![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)

An AI-powered data analysis and business intelligence platform. Sign up, upload a CSV/Excel file, and get automatic data profiling, natural-language querying, AI-style insights, forecasting, anomaly detection, customer segmentation, and one-click exportable reports — all backed by real Pandas computation, **never LLM-hallucinated numbers.**

## Why VERIDEXA is different

Most "chat with your data" tools let an LLM guess at numbers, which makes them unreliable past a demo. VERIDEXA keeps a hard separation: **only `modules/query_engine.py` is allowed to produce a number**, and it does so by parsing a question into a validated plan (operation + real column names, checked against the live dataset) and then running actual Pandas aggregation. The "AI Analyst" only ever *phrases* numbers that have already been computed — it never invents one. This means the app is **100% functional with zero API keys** — no LLM subscription required.

## What's built and working

- 🔐 **Full auth flow** — sign up / log in / log out, hashed + salted passwords (PBKDF2-HMAC-SHA256, stdlib-only), a change-password flow, temporary account lockout after repeated failed logins, and an enforced session timeout — backed by a local SQLite `users` table with WAL mode for safe concurrent multi-user access.
- 📂 **Upload & Clean** — CSV / Excel / JSON / Parquet upload (up to several GB, configurable) with validation, encoding/delimiter sniffing, automatic dtype inference, missing-value/duplicate/outlier detection, and one-click cleaning actions (drop dupes, fill strategies, outlier capping/removal, type conversion).
- 🔗 **Combine / Join** — load several files into one session and join any two of them (inner/left/right/outer) on matching key columns, producing a new table you can analyze, export, or join again.
- 💾 **Persistent storage** — optionally save any dataset (raw upload or joined result) to your account as Parquet-in-SQLite, so it's still there next time you log in from any machine — on top of the default fast, in-memory-only session mode.
- 🔍 **Data Explorer** — full profiling dashboard (overview, data quality, numeric stats, categorical breakdowns) with interactive filters (date range + up to 5 auto-detected category columns + a numeric range).
- 📊 **Analytics Dashboard** — auto-adapting KPI cards and trend/breakdown charts that gracefully skip whatever columns a given dataset doesn't have.
- 🤖 **AI Analyst** — a chat interface that answers plain-English questions via the validated query engine, with a four-part **Finding / Explanation / Business Impact / Recommendation** insight for every answer, auto-picked chart, and simple conversational memory (resolves "it"/"that" to the last metric discussed). Optional LLM-powered rephrasing supports Groq, OpenAI, Anthropic, or a local Ollama server — the app is 100% functional with none of them configured.
- 📈 **Automated EDA** — one-click report: correlations, outliers, key findings, and recommendations, all derived from real computed facts.
- 🔮 **Forecasting** — explainable linear-trend projection (OLS) with a widening confidence band, or a Holt-Winters seasonal model (trend + repeating cycle) with an inspectable trend/seasonal/residual decomposition chart — both ship with a clear "not a guarantee" disclaimer.
- ⚠️ **Anomaly Detection** — IQR-based outlier flagging with a per-record risk level and a plain-language reason.
- 👥 **Customer Segmentation** — RFM (Recency/Frequency/Monetary) rule-based segments with written explanations, or K-Means clustering on any two numeric columns.
- 💡 **AI Recommendations** — a prioritized action list synthesized from whatever analysis you've already run this session.
- 📄 **Reports** — export any table as CSV/Excel, plus a combined full-session report as HTML or a **native PDF** (no browser print dialog needed).
- ✅ **Tested + CI** — a pytest suite covering the loader, profiler, query engine, forecasting, anomaly detection, segmentation, and auth modules, run automatically on every push via GitHub Actions across Python 3.10–3.12.
- 🔒 **Security basics** — every column reference in a query plan is re-validated against the live DataFrame right before execution (defense in depth), no `eval`/blind code execution anywhere, input validation on signup, and a real logging layer under `logs/app.log`.

## Architecture

```
Question (English) → query_engine.build_plan() → validated QueryPlan
                                                        │
                                             query_engine.execute_plan()
                                                        │
                                          real Pandas aggregation (the ONLY
                                           place a number is computed)
                                                        │
                                          insight_generator.narrate()
                                     (phrases the facts — never invents one)
```

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Frontend | Streamlit |
| Data | Pandas, NumPy, PyArrow (Parquet) |
| Auth + storage DB | SQLite in WAL mode (`veridexa.db`, stdlib `sqlite3`) — accounts, audit log, and saved datasets |
| Visualization | Plotly |
| Machine Learning | scikit-learn (K-Means) |
| Forecasting | NumPy OLS linear regression, statsmodels Holt-Winters + seasonal decomposition |
| Report export | HTML, Excel (openpyxl), native PDF (xhtml2pdf) |
| Password hashing | stdlib `hashlib` (PBKDF2-HMAC-SHA256) — no extra crypto dependency |
| Testing / CI | pytest, GitHub Actions |

## Installation

```bash
# from the VERIDEXA/ folder
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Optional — copy `.env.example` to `.env` if you want to later enable LLM-powered rephrasing of insights (fully optional; the app works without it):

```bash
cp .env.example .env
```

## Run it

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). You'll land on the VERIDEXA sign-up/login screen first — create an account to get started.

## Run the tests

```bash
pytest
```

## Example questions to try in the AI Analyst

- What is the total revenue?
- Which region generated the highest revenue?
- What is the monthly revenue trend?
- Is there a correlation between quantity and profit?
- Average profit
- Top 5 category by revenue
- (follow-up) what about its monthly trend?

## Project structure

```
VERIDEXA/
├── app.py                        # Streamlit entry point — auth gate + all page routing
├── requirements.txt
├── .env.example
├── pytest.ini
│
├── .streamlit/
│   └── config.toml               # Dark theme
│
├── config/
│   └── settings.py                # Central config, reads .env
│
├── modules/
│   ├── db.py                      # SQLite connection + schema (users, audit_log, ...)
│   ├── auth.py                    # Signup/login/password hashing — the auth backbone
│   ├── ui_auth.py                 # Landing page + login/signup screens (Streamlit UI)
│   ├── data_loader.py             # File ingestion + validation + dtype inference
│   ├── data_cleaner.py            # Cleaning actions (dupes, missing, outliers, types)
│   ├── data_profiler.py           # Profiling stats (overview, quality, numeric, categorical)
│   ├── filters.py                 # Reusable interactive filter widgets
│   ├── dashboard.py               # Analytics Dashboard rendering
│   ├── query_engine.py            # ⭐ The validated NL→Pandas backbone (AI Analyst core)
│   ├── insight_generator.py       # Four-part Finding/Explanation/Impact/Recommendation
│   ├── ai_analyzer.py             # Optional LLM phrasing layer (off by default)
│   ├── eda_generator.py           # Automated EDA report
│   ├── forecasting.py             # Linear-trend forecasting with confidence bands
│   ├── anomaly_detection.py       # IQR-based anomaly flagging
│   ├── segmentation.py            # RFM + K-Means customer segmentation
│   ├── recommendation_engine.py   # Prioritized action list synthesis
│   ├── report_generator.py        # CSV/Excel/HTML export
│   └── visualization.py           # Centralized Plotly chart builders
│
├── utils/
│   ├── logger.py
│   ├── validators.py
│   └── helpers.py
│
├── tests/
│   ├── conftest.py
│   ├── test_data_loader.py
│   ├── test_profiler.py
│   ├── test_query_engine.py
│   ├── test_forecasting.py
│   ├── test_anomaly_segmentation.py
│   └── test_auth.py
│
└── logs/
    └── app.log                    # Runtime log (gitignored)
```

## Roadmap (not yet built)

The original spec sketched 50 stretch features (live DB/API connectors, SHAP feature importance, ARIMA/Prophet, RBAC, audit dashboards, PPT export, multi-tenant support, etc.). This build focuses on a solid, fully-working core end-to-end rather than spreading thin across all fifty. Natural next additions, in rough priority order:

1. True external data connectors (Google Sheets / Postgres / MySQL) via `connectors/`
2. Swap in a real LLM for `ai_analyzer.py` phrasing (Groq/OpenAI/Anthropic/local Ollama — the abstraction is already there)
3. Role-based access control + audit log viewer in the UI (the `audit_log` table already exists)
4. PDF/PowerPoint export alongside the existing CSV/Excel/HTML
5. Scheduled email/Slack report delivery
6. CI pipeline running `pytest` on every push

## Security notes

- Passwords are never stored in plaintext; PBKDF2-HMAC-SHA256 with a unique random salt per user and 260,000 iterations.
- Every AI Analyst query is executed through a validator that re-checks every column name against the live DataFrame immediately before running — a malformed or malicious question simply gets a friendly error, never a code path to arbitrary execution.
- This is a portfolio/demo app: the SQLite auth DB is local and unencrypted at rest, and there's no HTTPS/session-cookie hardening layer — don't use it to store real user data in production without adding those.
