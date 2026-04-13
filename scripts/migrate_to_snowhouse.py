"""
Migrate AEO benchmark data from DevRel (SFDEVREL) to Snowhouse.

Source: devrel connection → AEO_OBSERVABILITY.EVAL_SCHEMA
Target: my-snowflake connection → DEVREL.CNANTASENAMAT_DEV
Role:   DEVREL_INGEST_RL (inherits CNANTASENAMAT_DEV_OWNER database role)

Usage:
    python3 migrate_to_snowhouse.py
    python3 migrate_to_snowhouse.py --dry-run   # show DDL only, no execution
"""

import argparse
import sys
import time

import snowflake.connector

# ---------------------------------------------------------------------------
# Connection config
# ---------------------------------------------------------------------------

SOURCE = {
    "connection_name": "devrel",
    "warehouse": "COMPUTE_WH",
    "database": "AEO_OBSERVABILITY",
    "schema": "EVAL_SCHEMA",
}

TARGET = {
    "connection_name": "my-snowflake",
    "role": "DEVREL_INGEST_RL",
    "warehouse": "SNOWADHOC",
    "database": "DEVREL",
    "schema": "CNANTASENAMAT_DEV",
}

# ---------------------------------------------------------------------------
# Table DDLs (exact column order from source)
# ---------------------------------------------------------------------------

TABLE_DDLS = {
    "AEO_QUESTIONS": """
CREATE TABLE IF NOT EXISTS AEO_QUESTIONS (
    QUESTION_ID VARCHAR(10),
    QUESTION_TEXT VARCHAR(2000),
    CATEGORY VARCHAR(100),
    QUESTION_TYPE VARCHAR(20),
    CANONICAL_ANSWER VARCHAR(16000),
    MUST_HAVE_1 VARCHAR(500),
    MUST_HAVE_2 VARCHAR(500),
    MUST_HAVE_3 VARCHAR(500),
    MUST_HAVE_4 VARCHAR(500),
    MUST_HAVE_5 VARCHAR(500),
    DOC_URL VARCHAR(500)
)""",
    "AEO_RUNS": """
CREATE TABLE IF NOT EXISTS AEO_RUNS (
    RUN_ID NUMBER(38,0),
    RUN_DATE TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    DESCRIPTION VARCHAR(1000),
    DOMAIN_PROMPT BOOLEAN,
    CITATION BOOLEAN,
    AGENTIC BOOLEAN,
    SELF_CRITIQUE BOOLEAN,
    MODEL VARCHAR(100)
)""",
    "AEO_RUN_CONFIG": """
CREATE TABLE IF NOT EXISTS AEO_RUN_CONFIG (
    RUN_ID NUMBER(38,0) NOT NULL,
    MODEL VARCHAR(100) NOT NULL,
    DOMAIN_PROMPT BOOLEAN DEFAULT FALSE,
    CITE BOOLEAN DEFAULT FALSE,
    JUDGE_MODELS VARCHAR(500) DEFAULT 'openai-gpt-5.4,claude-opus-4-6,llama4-maverick',
    MAX_TOKENS NUMBER(38,0) DEFAULT 8192,
    STATUS VARCHAR(20) DEFAULT 'PENDING',
    CREATED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (RUN_ID)
)""",
    "AEO_RESPONSES": """
CREATE TABLE IF NOT EXISTS AEO_RESPONSES (
    RUN_ID NUMBER(38,0),
    QUESTION_ID VARCHAR(10),
    RESPONSE_TEXT VARCHAR(65000),
    GENERATED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP()
)""",
    "AEO_SCORES": """
CREATE TABLE IF NOT EXISTS AEO_SCORES (
    RUN_ID NUMBER(38,0),
    QUESTION_ID VARCHAR(10),
    JUDGE_MODEL VARCHAR(100),
    CORRECTNESS FLOAT,
    COMPLETENESS FLOAT,
    RECENCY FLOAT,
    CITATION FLOAT,
    RECOMMENDATION FLOAT,
    TOTAL_SCORE FLOAT,
    MUST_HAVE_1 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_2 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_3 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_4 BOOLEAN DEFAULT FALSE,
    MUST_HAVE_PASS FLOAT,
    RAW_JUDGE_RESPONSE VARCHAR(65000),
    SCORED_AT TIMESTAMP_NTZ(9) DEFAULT CURRENT_TIMESTAMP(),
    MUST_HAVE_5 BOOLEAN DEFAULT FALSE
)""",
}

# Column lists for explicit INSERT (avoids column-order gotchas)
TABLE_COLUMNS = {
    "AEO_QUESTIONS": [
        "QUESTION_ID", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
        "CANONICAL_ANSWER", "MUST_HAVE_1", "MUST_HAVE_2", "MUST_HAVE_3",
        "MUST_HAVE_4", "MUST_HAVE_5", "DOC_URL",
    ],
    "AEO_RUNS": [
        "RUN_ID", "RUN_DATE", "DESCRIPTION", "DOMAIN_PROMPT",
        "CITATION", "AGENTIC", "SELF_CRITIQUE", "MODEL",
    ],
    "AEO_RUN_CONFIG": [
        "RUN_ID", "MODEL", "DOMAIN_PROMPT", "CITE", "JUDGE_MODELS",
        "MAX_TOKENS", "STATUS", "CREATED_AT",
    ],
    "AEO_RESPONSES": [
        "RUN_ID", "QUESTION_ID", "RESPONSE_TEXT", "GENERATED_AT",
    ],
    "AEO_SCORES": [
        "RUN_ID", "QUESTION_ID", "JUDGE_MODEL", "CORRECTNESS",
        "COMPLETENESS", "RECENCY", "CITATION", "RECOMMENDATION",
        "TOTAL_SCORE", "MUST_HAVE_1", "MUST_HAVE_2", "MUST_HAVE_3",
        "MUST_HAVE_4", "MUST_HAVE_PASS", "RAW_JUDGE_RESPONSE",
        "SCORED_AT", "MUST_HAVE_5",
    ],
}

# Batch sizes for INSERT (large VARCHAR tables use smaller batches)
BATCH_SIZES = {
    "AEO_QUESTIONS": 128,
    "AEO_RUNS": 16,
    "AEO_RUN_CONFIG": 28,
    "AEO_RESPONSES": 50,
    "AEO_SCORES": 200,
}

# Expected row counts for verification
EXPECTED_COUNTS = {
    "AEO_QUESTIONS": 128,
    "AEO_RUNS": 16,
    "AEO_RUN_CONFIG": 28,
    "AEO_RESPONSES": 2048,
    "AEO_SCORES": 6144,
}

# ---------------------------------------------------------------------------
# View DDLs (rewritten for DEVREL.CNANTASENAMAT_DEV schema)
# ---------------------------------------------------------------------------

SCHEMA_PREFIX = "DEVREL.CNANTASENAMAT_DEV"

VIEW_DDLS = {
    "V_AEO_LEADERBOARD": f"""
CREATE OR REPLACE VIEW V_AEO_LEADERBOARD AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS
    FROM {SCHEMA_PREFIX}.AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
)
SELECT r.RUN_ID, r.DESCRIPTION, r.DOMAIN_PROMPT, r.CITATION,
       r.AGENTIC, r.SELF_CRITIQUE, r.MODEL,
       ROUND(SUM(ja.TOTAL_SCORE), 1) AS TOTAL_SCORE,
       ROUND(SUM(ja.TOTAL_SCORE) / (COUNT(DISTINCT ja.QUESTION_ID) * 50.0) * 100, 1) AS SCORE_PCT,
       ROUND(SUM(ja.MUST_HAVE_PASS), 1) AS TOTAL_MH_PASS,
       ROUND(SUM(ja.MUST_HAVE_PASS) / COUNT(DISTINCT ja.QUESTION_ID) * 100, 1) AS MH_PCT,
       COUNT(DISTINCT ja.QUESTION_ID) AS QUESTIONS_SCORED,
       COUNT(DISTINCT ja.QUESTION_ID) * 50.0 AS MAX_SCORE
FROM {SCHEMA_PREFIX}.AEO_RUNS r
JOIN judge_avg ja ON r.RUN_ID = ja.RUN_ID
GROUP BY r.RUN_ID, r.DESCRIPTION, r.DOMAIN_PROMPT, r.CITATION,
         r.AGENTIC, r.SELF_CRITIQUE, r.MODEL
ORDER BY SCORE_PCT DESC""",

    "V_AEO_FACTORIAL_EFFECTS": f"""
CREATE OR REPLACE VIEW V_AEO_FACTORIAL_EFFECTS AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS
    FROM {SCHEMA_PREFIX}.AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
),
run_totals AS (
    SELECT r.RUN_ID, r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE,
           ROUND(SUM(ja.TOTAL_SCORE) / (COUNT(DISTINCT ja.QUESTION_ID) * 50.0) * 100, 1) AS SCORE_PCT,
           ROUND(SUM(ja.MUST_HAVE_PASS) / COUNT(DISTINCT ja.QUESTION_ID) * 100, 1) AS MH_PCT
    FROM {SCHEMA_PREFIX}.AEO_RUNS r
    JOIN judge_avg ja ON r.RUN_ID = ja.RUN_ID
    GROUP BY r.RUN_ID, r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE
)
SELECT 'Domain Prompt' AS FACTOR,
       ROUND(AVG(CASE WHEN DOMAIN_PROMPT THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT DOMAIN_PROMPT THEN SCORE_PCT END), 1) AS SCORE_EFFECT_PP,
       ROUND(AVG(CASE WHEN DOMAIN_PROMPT THEN MH_PCT END)
           - AVG(CASE WHEN NOT DOMAIN_PROMPT THEN MH_PCT END), 1) AS MH_EFFECT_PP
FROM run_totals
UNION ALL
SELECT 'Citation',
       ROUND(AVG(CASE WHEN CITATION THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT CITATION THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN CITATION THEN MH_PCT END)
           - AVG(CASE WHEN NOT CITATION THEN MH_PCT END), 1)
FROM run_totals
UNION ALL
SELECT 'Agentic',
       ROUND(AVG(CASE WHEN AGENTIC THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT AGENTIC THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN AGENTIC THEN MH_PCT END)
           - AVG(CASE WHEN NOT AGENTIC THEN MH_PCT END), 1)
FROM run_totals
UNION ALL
SELECT 'Self-Critique',
       ROUND(AVG(CASE WHEN SELF_CRITIQUE THEN SCORE_PCT END)
           - AVG(CASE WHEN NOT SELF_CRITIQUE THEN SCORE_PCT END), 1),
       ROUND(AVG(CASE WHEN SELF_CRITIQUE THEN MH_PCT END)
           - AVG(CASE WHEN NOT SELF_CRITIQUE THEN MH_PCT END), 1)
FROM run_totals""",

    "V_AEO_PER_QUESTION_HEATMAP": f"""
CREATE OR REPLACE VIEW V_AEO_PER_QUESTION_HEATMAP AS
WITH judge_avg AS (
    SELECT RUN_ID, QUESTION_ID,
           AVG(TOTAL_SCORE) AS TOTAL_SCORE,
           AVG(MUST_HAVE_PASS) AS MUST_HAVE_PASS,
           AVG(CORRECTNESS) AS CORRECTNESS,
           AVG(COMPLETENESS) AS COMPLETENESS,
           AVG(RECENCY) AS RECENCY,
           AVG(CITATION) AS CITATION_SCORE,
           AVG(RECOMMENDATION) AS RECOMMENDATION
    FROM {SCHEMA_PREFIX}.AEO_SCORES
    GROUP BY RUN_ID, QUESTION_ID
)
SELECT ja.QUESTION_ID, q.CATEGORY, q.QUESTION_TYPE, ja.RUN_ID,
       r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE,
       ja.TOTAL_SCORE, ja.MUST_HAVE_PASS,
       ja.CORRECTNESS, ja.COMPLETENESS, ja.RECENCY,
       ja.CITATION_SCORE, ja.RECOMMENDATION
FROM judge_avg ja
JOIN {SCHEMA_PREFIX}.AEO_QUESTIONS q ON ja.QUESTION_ID = q.QUESTION_ID
JOIN {SCHEMA_PREFIX}.AEO_RUNS r ON ja.RUN_ID = r.RUN_ID
ORDER BY ja.QUESTION_ID, ja.RUN_ID""",

    "V_AEO_JUDGE_AGREEMENT": f"""
CREATE OR REPLACE VIEW V_AEO_JUDGE_AGREEMENT AS
WITH per_judge AS (
    SELECT RUN_ID, QUESTION_ID, JUDGE_MODEL, TOTAL_SCORE, MUST_HAVE_PASS
    FROM {SCHEMA_PREFIX}.AEO_SCORES
),
judge_pairs AS (
    SELECT a.RUN_ID, a.QUESTION_ID,
           a.JUDGE_MODEL AS JUDGE_A, b.JUDGE_MODEL AS JUDGE_B,
           a.TOTAL_SCORE AS SCORE_A, b.TOTAL_SCORE AS SCORE_B,
           ABS(a.TOTAL_SCORE - b.TOTAL_SCORE) AS SCORE_DIFF
    FROM per_judge a
    JOIN per_judge b ON a.RUN_ID = b.RUN_ID AND a.QUESTION_ID = b.QUESTION_ID
         AND a.JUDGE_MODEL < b.JUDGE_MODEL
)
SELECT RUN_ID, JUDGE_A, JUDGE_B, COUNT(*) AS N_QUESTIONS,
       ROUND(AVG(SCORE_DIFF), 2) AS AVG_SCORE_DIFF,
       ROUND(CORR(SCORE_A, SCORE_B), 3) AS PEARSON_CORRELATION,
       SUM(CASE WHEN SCORE_DIFF <= 1 THEN 1 ELSE 0 END) AS AGREE_WITHIN_1PT,
       SUM(CASE WHEN SCORE_DIFF = 0 THEN 1 ELSE 0 END) AS EXACT_AGREE
FROM judge_pairs
GROUP BY RUN_ID, JUDGE_A, JUDGE_B""",
}

# Table migration order (small tables first, large last)
TABLE_ORDER = ["AEO_QUESTIONS", "AEO_RUNS", "AEO_RUN_CONFIG", "AEO_RESPONSES", "AEO_SCORES"]


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------

def connect(cfg):
    """Open a Snowflake connection using the given config."""
    conn = snowflake.connector.connect(connection_name=cfg["connection_name"])
    cur = conn.cursor()
    if "role" in cfg:
        cur.execute(f"USE ROLE {cfg['role']}")
    cur.execute(f"USE WAREHOUSE {cfg['warehouse']}")
    cur.execute(f"USE DATABASE {cfg['database']}")
    cur.execute(f"USE SCHEMA {cfg['schema']}")
    return conn


def create_tables(tgt_cur, dry_run=False):
    """Create all tables on the target."""
    for table in TABLE_ORDER:
        ddl = TABLE_DDLS[table]
        print(f"  CREATE TABLE {table} ... ", end="", flush=True)
        if dry_run:
            print("(dry-run)")
            print(f"    {ddl.strip()}")
        else:
            tgt_cur.execute(ddl)
            print("OK")


def transfer_table(src_conn, tgt_conn, table, dry_run=False):
    """Read all rows from source and batch-insert into target."""
    cols = TABLE_COLUMNS[table]
    batch_size = BATCH_SIZES[table]
    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    select_sql = f"SELECT {col_list} FROM {table}"
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    src_cur = src_conn.cursor()
    src_cur.execute(select_sql)
    rows = src_cur.fetchall()
    total = len(rows)
    print(f"  {table}: {total} rows read from source", flush=True)

    if dry_run:
        print(f"    (dry-run) Would insert {total} rows in batches of {batch_size}")
        return total

    tgt_cur = tgt_conn.cursor()
    inserted = 0
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        tgt_cur.executemany(insert_sql, batch)
        inserted += len(batch)
        if total > batch_size:
            print(f"    {inserted}/{total} rows inserted", flush=True)

    print(f"    {inserted} rows inserted OK", flush=True)
    return inserted


def create_views(tgt_cur, dry_run=False):
    """Create all views on the target."""
    for view_name, ddl in VIEW_DDLS.items():
        print(f"  CREATE VIEW {view_name} ... ", end="", flush=True)
        if dry_run:
            print("(dry-run)")
        else:
            tgt_cur.execute(ddl)
            print("OK")


def verify(tgt_conn):
    """Verify row counts on the target match expected."""
    tgt_cur = tgt_conn.cursor()
    all_ok = True
    print("\nVerification:")
    for table in TABLE_ORDER:
        tgt_cur.execute(f"SELECT COUNT(*) FROM {table}")
        actual = tgt_cur.fetchone()[0]
        expected = EXPECTED_COUNTS[table]
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_ok = False
        print(f"  {table}: {actual} rows (expected {expected}) [{status}]")

    # Quick view smoke test
    print("\nView smoke test:")
    tgt_cur.execute("SELECT COUNT(*) FROM V_AEO_LEADERBOARD")
    lb_cnt = tgt_cur.fetchone()[0]
    print(f"  V_AEO_LEADERBOARD: {lb_cnt} rows")
    tgt_cur.execute("SELECT COUNT(*) FROM V_AEO_FACTORIAL_EFFECTS")
    fe_cnt = tgt_cur.fetchone()[0]
    print(f"  V_AEO_FACTORIAL_EFFECTS: {fe_cnt} rows")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Migrate AEO data to Snowhouse")
    parser.add_argument("--dry-run", action="store_true", help="Show DDL/SQL without executing")
    args = parser.parse_args()

    print("=" * 60)
    print("AEO Benchmark Migration: DevRel → Snowhouse")
    print("=" * 60)
    print(f"Source: {SOURCE['connection_name']} / {SOURCE['database']}.{SOURCE['schema']}")
    print(f"Target: {TARGET['connection_name']} / {TARGET['database']}.{TARGET['schema']}")
    print(f"Role:   {TARGET['role']}")
    print()

    # Connect
    print("Connecting to source ...", flush=True)
    src_conn = connect(SOURCE)
    print("Connecting to target ...", flush=True)
    tgt_conn = connect(TARGET)

    tgt_cur = tgt_conn.cursor()

    # Step 1: Create tables
    print("\n--- Creating tables ---")
    create_tables(tgt_cur, dry_run=args.dry_run)

    # Step 2: Transfer data
    print("\n--- Transferring data ---")
    t0 = time.time()
    for table in TABLE_ORDER:
        transfer_table(src_conn, tgt_conn, table, dry_run=args.dry_run)
    elapsed = time.time() - t0
    print(f"\nData transfer completed in {elapsed:.1f}s")

    # Step 3: Create views
    print("\n--- Creating views ---")
    create_views(tgt_cur, dry_run=args.dry_run)

    # Step 4: Verify
    if not args.dry_run:
        all_ok = verify(tgt_conn)
        if all_ok:
            print("\nMigration completed successfully.")
        else:
            print("\nMigration completed with MISMATCHES — investigate above.")
            sys.exit(1)
    else:
        print("\nDry run complete. No changes made.")

    src_conn.close()
    tgt_conn.close()


if __name__ == "__main__":
    main()
