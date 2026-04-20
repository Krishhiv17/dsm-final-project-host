"""
tools.py — Database query tools exposed to the LLM via Groq function calling.
Only SELECT queries are permitted; results are returned as markdown tables.
"""

import json
import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "db" / "air_health.db"

# ── Tool schema (OpenAI / Groq format) ───────────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Run a read-only SQL SELECT query against the air quality & public health "
                "database for Indian districts (2018-2023). Use this whenever the user asks "
                "for specific numbers, district details, rankings, trends, or any data that "
                "requires querying the database.\n\n"
                "TABLES:\n"
                "  districts(district_id PK, district_name, state, population, area_sq_km,\n"
                "            density_per_sq_km, literacy_rate, urban_percentage)\n\n"
                "  air_quality(id PK, district_id FK, date TEXT 'YYYY-MM-DD',\n"
                "              pm25, pm10, no2, so2, aqi)\n\n"
                "  health_indicators(id PK, district_id FK, year_month TEXT 'YYYY-MM',\n"
                "                    respiratory_cases, cardiovascular_cases,\n"
                "                    diarrhoea_cases, total_opd_visits,\n"
                "                    institutional_deliveries, immunization_doses)\n\n"
                "  water_quality(id PK, district_id FK, year, quarter, ph,\n"
                "                dissolved_oxygen_mg_l, bod_mg_l, total_coliform_mpn,\n"
                "                turbidity_ntu, tds_mg_l)\n\n"
                "TIPS:\n"
                "  - Always JOIN districts to get district_name and state.\n"
                "  - Use LIMIT 20 for row-level queries; omit for aggregations.\n"
                "  - Date filter: WHERE date BETWEEN '2022-01-01' AND '2022-12-31'\n"
                "  - Year-month filter: WHERE year_month LIKE '2022-%'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Valid SQLite SELECT statement to execute.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-line plain-English description of what this query answers.",
                    },
                },
                "required": ["sql", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overview_stats",
            "description": (
                "Return a pre-computed summary of the entire dataset — national averages, "
                "min/max pollution, worst/best states, top disease-burden districts, and "
                "date range. Use for general overview or high-level summary questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────
def execute_tool(name: str, inputs: dict) -> str:
    if name == "query_database":
        return _run_query(inputs["sql"], inputs.get("description", ""))
    if name == "get_overview_stats":
        return _overview_stats()
    return f"Unknown tool: {name}"


def execute_tool_call(tool_call) -> str:
    """Convenience wrapper that accepts a Groq ToolCall object."""
    name = tool_call.function.name
    inputs = json.loads(tool_call.function.arguments)
    return execute_tool(name, inputs)


# ── Internal implementations ──────────────────────────────────────────────────
def _run_query(sql: str, description: str) -> str:
    sql = sql.strip()

    if not sql.upper().lstrip().startswith("SELECT"):
        return "Error: Only SELECT queries are permitted."

    blocked = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
               "ATTACH", "DETACH", "PRAGMA", "VACUUM"}
    if blocked & set(sql.upper().split()):
        return f"Error: Forbidden keyword(s) detected."

    if not DB_PATH.exists():
        return "Error: Database not found. Run `python src/03_database.py` first."

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
        note = f"\n\n*Showing 25 of {len(df)} total rows.*"
        df = df.head(25)

    try:
        table = df.to_markdown(index=False)
    except Exception:
        table = df.to_string(index=False)

    return f"**{description}**\n\n{table}{note}"


def _overview_stats() -> str:
    if not DB_PATH.exists():
        return "Database not found. Run `python src/03_database.py` first."

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        districts = pd.read_sql_query(
            "SELECT COUNT(*) n, COUNT(DISTINCT state) states FROM districts", conn
        ).iloc[0].to_dict()

        aq = pd.read_sql_query(
            """SELECT COUNT(*) records, ROUND(AVG(pm25),1) avg_pm25,
                      ROUND(MIN(pm25),1) min_pm25, ROUND(MAX(pm25),1) max_pm25,
                      ROUND(AVG(aqi),0) avg_aqi, MIN(date) earliest, MAX(date) latest
               FROM air_quality""",
            conn,
        ).iloc[0].to_dict()

        health = pd.read_sql_query(
            """SELECT ROUND(AVG(respiratory_cases),0) avg_resp,
                      SUM(respiratory_cases) total_resp,
                      SUM(cardiovascular_cases) total_cardio
               FROM health_indicators""",
            conn,
        ).iloc[0].to_dict()

        worst = pd.read_sql_query(
            """SELECT d.state, ROUND(AVG(a.pm25),1) avg_pm25
               FROM air_quality a JOIN districts d USING(district_id)
               GROUP BY d.state ORDER BY avg_pm25 DESC LIMIT 5""",
            conn,
        )
        best = pd.read_sql_query(
            """SELECT d.state, ROUND(AVG(a.pm25),1) avg_pm25
               FROM air_quality a JOIN districts d USING(district_id)
               GROUP BY d.state ORDER BY avg_pm25 LIMIT 5""",
            conn,
        )
        top_disease = pd.read_sql_query(
            """SELECT d.district_name, d.state,
                      ROUND(AVG(h.respiratory_cases),0) avg_resp
               FROM health_indicators h JOIN districts d USING(district_id)
               GROUP BY d.district_id ORDER BY avg_resp DESC LIMIT 5""",
            conn,
        )
    finally:
        conn.close()

    return f"""**Dataset Overview**

- **Districts:** {int(districts['n'])} across {int(districts['states'])} states
- **Air quality records:** {int(aq['records']):,} daily observations ({aq['earliest']} → {aq['latest']})
- **National avg PM2.5:** {aq['avg_pm25']} µg/m³ (min {aq['min_pm25']}, max {aq['max_pm25']}) — NAAQS limit 60 µg/m³
- **National avg AQI:** {int(aq['avg_aqi'])}
- **Total respiratory cases:** {int(health['total_resp']):,} (avg {int(health['avg_resp'])}/district-month)
- **Total cardiovascular cases:** {int(health['total_cardio']):,}

**Most polluted states:**
{worst.to_markdown(index=False)}

**Cleanest states:**
{best.to_markdown(index=False)}

**Highest disease-burden districts:**
{top_disease.to_markdown(index=False)}
"""
