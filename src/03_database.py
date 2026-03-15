"""
03_database.py
==============
Database Design & Implementation

Creates an SQLite database (db/air_health.db) with:
  - districts          → District demographics
  - air_quality        → Daily pollutant measurements
  - health_indicators  → Monthly HMIS health reports
  - water_quality      → Quarterly water quality measurements

Also creates useful views and demonstrates analytical queries.
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DB_PATH = PROJECT_ROOT / "db" / "air_health.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def create_schema(conn):
    """Create database tables with proper schema and constraints."""
    cursor = conn.cursor()

    # ── Districts table ─────────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS districts (
        district_id    INTEGER PRIMARY KEY,
        district_name  TEXT NOT NULL,
        state          TEXT NOT NULL,
        population     INTEGER,
        area_sq_km     INTEGER,
        density_per_sq_km REAL,
        literacy_rate  REAL,
        urban_percentage REAL
    );
    """)

    # ── Air Quality table ───────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS air_quality (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        district_id INTEGER NOT NULL,
        date        TEXT NOT NULL,
        pm25        REAL,
        pm10        REAL,
        no2         REAL,
        so2         REAL,
        aqi         INTEGER,
        FOREIGN KEY (district_id) REFERENCES districts(district_id)
    );
    """)

    # ── Health Indicators table ─────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS health_indicators (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        district_id           INTEGER NOT NULL,
        year_month            TEXT NOT NULL,
        respiratory_cases     INTEGER,
        cardiovascular_cases  INTEGER,
        diarrhoea_cases       INTEGER,
        total_opd_visits      INTEGER,
        institutional_deliveries INTEGER,
        immunization_doses    INTEGER,
        FOREIGN KEY (district_id) REFERENCES districts(district_id)
    );
    """)

    # ── Water Quality table ─────────────────────────────────────
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS water_quality (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        district_id           INTEGER NOT NULL,
        year                  INTEGER NOT NULL,
        quarter               INTEGER NOT NULL,
        ph                    REAL,
        dissolved_oxygen_mg_l REAL,
        bod_mg_l              REAL,
        total_coliform_mpn    INTEGER,
        turbidity_ntu         REAL,
        tds_mg_l              REAL,
        FOREIGN KEY (district_id) REFERENCES districts(district_id)
    );
    """)

    # ── Indexes for performance ─────────────────────────────────
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_aq_district_date ON air_quality(district_id, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_health_district_month ON health_indicators(district_id, year_month);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wq_district ON water_quality(district_id, year, quarter);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_districts_state ON districts(state);")

    conn.commit()
    print("  → Schema created with 4 tables and 4 indexes")


def ingest_data(conn):
    """Load CSV data into SQLite tables."""
    # Districts
    df_dist = pd.read_csv(RAW_DIR / "districts.csv")
    df_dist.to_sql("districts", conn, if_exists="replace", index=False)
    print(f"  → Ingested {len(df_dist):,} districts")

    # Air Quality
    df_aq = pd.read_csv(RAW_DIR / "air_quality_daily.csv")
    df_aq.to_sql("air_quality", conn, if_exists="replace", index=False)
    print(f"  → Ingested {len(df_aq):,} air quality records")

    # Health
    df_health = pd.read_csv(RAW_DIR / "health_hmis_monthly.csv")
    df_health.to_sql("health_indicators", conn, if_exists="replace", index=False)
    print(f"  → Ingested {len(df_health):,} health records")

    # Water Quality
    df_wq = pd.read_csv(RAW_DIR / "water_quality.csv")
    df_wq.to_sql("water_quality", conn, if_exists="replace", index=False)
    print(f"  → Ingested {len(df_wq):,} water quality records")


def create_views(conn):
    """Create analytical views combining tables."""
    cursor = conn.cursor()

    # ── View 1: Monthly air quality summary per district ────────
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_monthly_air_quality AS
    SELECT
        d.district_id,
        d.district_name,
        d.state,
        strftime('%Y-%m', aq.date) AS year_month,
        ROUND(AVG(aq.pm25), 1) AS avg_pm25,
        ROUND(AVG(aq.pm10), 1) AS avg_pm10,
        ROUND(AVG(aq.no2), 1) AS avg_no2,
        ROUND(AVG(aq.so2), 1) AS avg_so2,
        ROUND(AVG(aq.aqi), 0) AS avg_aqi,
        COUNT(*) AS measurement_days
    FROM air_quality aq
    JOIN districts d ON aq.district_id = d.district_id
    GROUP BY d.district_id, d.district_name, d.state, strftime('%Y-%m', aq.date);
    """)

    # ── View 2: Combined air quality + health (monthly) ─────────
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_air_health_monthly AS
    SELECT
        maq.district_id,
        maq.district_name,
        maq.state,
        maq.year_month,
        maq.avg_pm25,
        maq.avg_pm10,
        maq.avg_no2,
        maq.avg_so2,
        maq.avg_aqi,
        h.respiratory_cases,
        h.cardiovascular_cases,
        h.diarrhoea_cases,
        h.total_opd_visits,
        d.population,
        d.urban_percentage,
        d.literacy_rate,
        ROUND(h.respiratory_cases * 100000.0 / d.population, 2) AS resp_rate_per_100k,
        ROUND(h.cardiovascular_cases * 100000.0 / d.population, 2) AS cardio_rate_per_100k
    FROM v_monthly_air_quality maq
    JOIN health_indicators h
        ON maq.district_id = h.district_id
        AND maq.year_month = h.year_month
    JOIN districts d ON maq.district_id = d.district_id;
    """)

    # ── View 3: Annual state-level summary ──────────────────────
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_state_annual_summary AS
    SELECT
        d.state,
        strftime('%Y', aq.date) AS year,
        COUNT(DISTINCT d.district_id) AS num_districts,
        ROUND(AVG(aq.pm25), 1) AS avg_pm25,
        ROUND(AVG(aq.pm10), 1) AS avg_pm10,
        ROUND(AVG(aq.no2), 1) AS avg_no2,
        SUM(h.respiratory_cases) AS total_respiratory,
        SUM(h.cardiovascular_cases) AS total_cardiovascular,
        SUM(d.population) / COUNT(DISTINCT d.district_id) AS avg_district_population
    FROM air_quality aq
    JOIN districts d ON aq.district_id = d.district_id
    LEFT JOIN health_indicators h
        ON d.district_id = h.district_id
        AND strftime('%Y-%m', aq.date) = h.year_month
    GROUP BY d.state, strftime('%Y', aq.date);
    """)

    conn.commit()
    print("  → Created 3 analytical views")


def run_demo_queries(conn):
    """Run and display sample analytical queries."""
    print("\n" + "=" * 60)
    print("  Demo Queries")
    print("=" * 60)

    # Query 1: Top 10 most polluted districts (annual avg PM2.5)
    print("\n  Q1: Top 10 Most Polluted Districts (Avg PM2.5, 2022)")
    q1 = pd.read_sql("""
    SELECT district_name, state, ROUND(AVG(pm25), 1) AS avg_pm25
    FROM air_quality aq
    JOIN districts d ON aq.district_id = d.district_id
    WHERE date LIKE '2022%'
    GROUP BY d.district_id
    ORDER BY avg_pm25 DESC
    LIMIT 10;
    """, conn)
    print(q1.to_string(index=False))

    # Query 2: Correlation proxy — avg PM2.5 vs respiratory cases by state
    print("\n  Q2: State-Level Avg PM2.5 vs Respiratory Cases (2022)")
    q2 = pd.read_sql("""
    SELECT state, avg_pm25, total_respiratory
    FROM v_state_annual_summary
    WHERE year = '2022'
    ORDER BY avg_pm25 DESC
    LIMIT 10;
    """, conn)
    print(q2.to_string(index=False))

    # Query 3: Seasonal pattern — monthly avg AQI across all districts
    print("\n  Q3: Monthly AQI Seasonality (All Districts, 2022)")
    q3 = pd.read_sql("""
    SELECT
        CAST(strftime('%m', date) AS INTEGER) AS month,
        ROUND(AVG(aqi), 0) AS avg_aqi,
        ROUND(AVG(pm25), 1) AS avg_pm25
    FROM air_quality
    WHERE date LIKE '2022%'
    GROUP BY strftime('%m', date)
    ORDER BY month;
    """, conn)
    print(q3.to_string(index=False))

    # Query 4: Districts with worst health outcomes and high pollution
    print("\n  Q4: High-Risk Districts (High Pollution + High Disease, 2022)")
    q4 = pd.read_sql("""
    SELECT
        district_name, state,
        ROUND(AVG(avg_pm25), 1) AS yearly_pm25,
        SUM(respiratory_cases) AS total_resp,
        SUM(cardiovascular_cases) AS total_cardio,
        ROUND(AVG(resp_rate_per_100k), 1) AS resp_rate_per_100k
    FROM v_air_health_monthly
    WHERE year_month LIKE '2022%'
    GROUP BY district_id
    HAVING yearly_pm25 > 60 AND total_resp > 500
    ORDER BY yearly_pm25 DESC
    LIMIT 10;
    """, conn)
    print(q4.to_string(index=False))


def main():
    print("=" * 60)
    print("  DSM Final Project — Database Design & Implementation")
    print("=" * 60)

    # Remove existing DB for clean rebuild
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"\n  Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    print(f"\n  Connected to: {DB_PATH}")

    print("\n[1/4] Creating schema...")
    create_schema(conn)

    print("\n[2/4] Ingesting data from CSVs...")
    ingest_data(conn)

    print("\n[3/4] Creating analytical views...")
    create_views(conn)

    print("\n[4/4] Running demo queries...")
    run_demo_queries(conn)

    # Database stats
    cursor = conn.cursor()
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    print(f"\n{'=' * 60}")
    print(f"  Database Ready: {DB_PATH}")
    print(f"  Tables: {', '.join(t[0] for t in tables)}")
    print(f"  File size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"{'=' * 60}")

    conn.close()


if __name__ == "__main__":
    main()
