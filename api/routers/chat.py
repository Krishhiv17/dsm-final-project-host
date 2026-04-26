"""LLM chat endpoint — Groq + SQL-in-codeblock loop over the project SQLite DB."""
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd

try:
    from groq import Groq
except ImportError:
    Groq = None  # type: ignore

router = APIRouter(prefix="/chat", tags=["chat"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "air_health.db"

SYSTEM_PROMPT = """You are an expert data analyst and research assistant embedded in an
interactive dashboard for the project "Air Quality & Public Health in Indian Districts."

## Your role
Answer questions about air pollution (PM2.5, PM10, NO₂, SO₂) and public health outcomes
(respiratory, cardiovascular, diarrhoeal diseases) across 150 Indian districts in 15 states,
covering daily data from 2018 to 2023. You have direct access to the project's SQLite
database via SQL queries.

## Project facts you always know
- **Coverage:** 150 districts, 15 states (Delhi, Maharashtra, UP, Bihar, West Bengal,
  Tamil Nadu, Rajasthan, Karnataka, Gujarat, MP, Andhra Pradesh, Telangana, Kerala,
  Punjab, Haryana)
- **NAAQS standards:** PM2.5 ≤ 60 µg/m³, PM10 ≤ 100 µg/m³, NO₂ ≤ 80 µg/m³, SO₂ ≤ 80 µg/m³
- **Key finding:** National PM2.5 has been flat (~59 µg/m³) from 2018–2023 — no improvement
  despite GRAP, BS-VI vehicles, odd-even schemes, crop-burning bans
- **Seasonal pattern:** Winter (Nov-Feb) shows 2-3× higher PM2.5 than monsoon (Jul-Sep)
  due to temperature inversions and crop stubble burning in Punjab/Haryana
- **Statistical results:**
  - PM2.5 ↔ Respiratory cases: Pearson r = 0.38, p ≈ 0 (highly significant)
  - Cohen's d = 0.55 (medium effect)
  - ANOVA across 15 states: F = 149.66, p ≈ 0
  - Granger causality: pollution leads disease, peak lag ~1 month
- **Causal estimates:**
  - Synthetic Control Method (New Delhi treated): ATT ≈ +76 respiratory cases/100k
  - Propensity Score Matching: ATT ≈ +41.5 cases/100k (95% CI: 40.3–42.7)
  - Regression Discontinuity at NAAQS 60 µg/m³: null result — no discrete threshold
- **ML models:** Random Forest R² = 0.81. Top features: population (59%), PM10 (23%), PM2.5 (8%)
- **Risk clusters (K=4):**
  - Cluster 1 "Critical-High Pollution" (~15 districts): avg PM2.5 ≈ 110 µg/m³, mainly Delhi/NCR
  - Cluster 3 "Critical-High Disease" (~18 districts): UP/Bihar, avg PM2.5 ≈ 70 but very high disease
  - Cluster 0 "At Risk" (~58 districts): moderate pollution & disease
  - Cluster 2 "Moderate" (~59 districts): southern/coastal states
- **Network:** 7 community zones spanning state boundaries; Moran's I ≈ 0.5 (strong spatial clustering)
- **Panel Fixed Effects:** PM2.5 coefficient ≈ +0.31 respiratory cases per unit increase (within-district)
- **Mediation:** ~38% of PM2.5 effect on respiratory disease is mediated through cardiovascular pathway

## Querying data
When you need specific numbers or data from the database, write a SQL SELECT query in a
fenced code block exactly like this:

```sql
SELECT ...
```

Rules:
- Write the SQL block and STOP — do not write the answer yet.
- The system executes the query and returns results automatically.
- Only SELECT statements are allowed. Always JOIN districts to get district_name/state.
- NEVER invent or estimate specific numbers — always query for them.
- After receiving all results, write a complete, well-formatted final answer.
- Sanity-check results: respiratory cases per district per month are 100–2000. If implausibly
  large, your JOIN likely overcounted — use AVG instead of SUM.

## Exact database schema (ONLY these column names)
```
districts        : district_id, district_name, state, population, area_sq_km,
                   density_per_sq_km, literacy_rate, urban_percentage
air_quality      : id, district_id, date (TEXT 'YYYY-MM-DD'), pm25, pm10, no2, so2, aqi
health_indicators: id, district_id, year_month (TEXT 'YYYY-MM'),
                   respiratory_cases, cardiovascular_cases, diarrhoea_cases,
                   total_opd_visits, institutional_deliveries, immunization_doses
water_quality    : id, district_id, year, quarter, ph, dissolved_oxygen_mg_l,
                   bod_mg_l, total_coliform_mpn, turbidity_ntu, tds_mg_l
```

NO pre-aggregated columns exist. Always compute: AVG(a.pm25), SUM(h.respiratory_cases), etc.

## Answering
1. Compare numbers against NAAQS standards, national averages, or seasonal norms.
2. Be concise but complete. Use bullet points and bold key numbers.
3. For policy questions, draw on: district-level GRAP, airshed governance, healthcare
   investment in high-burden districts, expanded CPCB monitoring.
4. Tone: professional, evidence-based, accessible. Explain acronyms on first use."""

# ── helpers ────────────────────────────────────────────────────────────────────

def _run_query(sql: str) -> str:
    sql = sql.strip()
    if not sql.upper().lstrip().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."
    blocked = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "ATTACH"}
    if blocked & set(sql.upper().split()):
        return "Error: Forbidden keyword detected."
    if not DB_PATH.exists():
        return "Error: Database not found."
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        df = pd.read_sql_query(sql, conn)
        conn.close()
    except Exception as exc:
        return f"Query error: {exc}"
    if df.empty:
        return "Query returned no results."
    note = ""
    if len(df) > 25:
        note = f"\n\n*Showing 25 of {len(df)} rows.*"
        df = df.head(25)
    try:
        return df.to_markdown(index=False) + note
    except Exception:
        return df.to_string(index=False) + note


def _extract_sql(text: str) -> list[str]:
    blocks = re.findall(r"```(?:sql|SQL)\s*(.*?)\s*```", text, re.DOTALL)
    return [b.strip() for b in blocks if b.strip().upper().startswith("SELECT")]


# ── request / response models ─────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Message]
    api_key: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    queries: list[str]


# ── endpoint ──────────────────────────────────────────────────────────────────

@router.post("/message", response_model=ChatResponse)
def chat_message(req: ChatRequest):
    if Groq is None:
        return ChatResponse(reply="Groq package not installed.", queries=[])

    api_key = req.api_key or os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return ChatResponse(reply="No GROQ_API_KEY configured.", queries=[])

    client = Groq(api_key=api_key)
    model = "llama-3.3-70b-versatile"

    loop_messages: list[dict] = [
        {"role": m.role, "content": m.content}
        for m in req.messages
        if m.role in ("user", "assistant")
    ]

    queries_log: list[str] = []

    for _ in range(4):
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + loop_messages,
            max_tokens=1024,
        )
        text = resp.choices[0].message.content or ""
        sql_blocks = _extract_sql(text)

        if not sql_blocks:
            break

        results_parts: list[str] = []
        has_error = False
        for sql in sql_blocks:
            queries_log.append(sql.replace("\n", " ")[:80])
            result = _run_query(sql)
            results_parts.append(result)
            if result.startswith("Query error:") or result.startswith("Error:"):
                has_error = True

        sql_only = "\n\n".join(f"```sql\n{s}\n```" for s in sql_blocks)
        loop_messages.append({"role": "assistant", "content": sql_only})

        feedback = (
            "One or more SQL queries failed:\n\n" + "\n\n---\n\n".join(results_parts)
            + "\n\nWrite a corrected SQL block."
            if has_error
            else "Query results:\n\n" + "\n\n---\n\n".join(results_parts)
        )
        loop_messages.append({"role": "user", "content": feedback})

    # Final answer pass
    if queries_log:
        loop_messages.append({
            "role": "user",
            "content": (
                "You now have all the data you need. Write your complete, well-formatted "
                "final answer. Do NOT output any SQL blocks — just plain text with markdown."
            ),
        })

    final = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}] + loop_messages,
        max_tokens=2048,
    )
    reply = final.choices[0].message.content or ""

    return ChatResponse(reply=reply, queries=queries_log)
