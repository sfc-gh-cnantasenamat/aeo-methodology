"""
AEO Benchmark SPCS Interactive Runner
Handles a single user-submitted question from the SiS app.

Triggered by AEO_TRIGGER_INTERACTIVE stored procedure via EXECUTE JOB SERVICE
with RUN_MODE=interactive. Reads the prompt from AEO_INTERACTIVE_RESULTS,
calls setup_cortex_connection_for_spcs() so CoCo has full tool access,
generates a response via the Cortex CLI (-p flag is required for headless
subprocess execution in non-TTY SPCS containers), then writes the result back.

Environment variables set by AEO_TRIGGER_INTERACTIVE SP:
  REQUEST_ID  - UUID for this request row in AEO_INTERACTIVE_RESULTS
  WAREHOUSE   - Snowflake warehouse (default: SNOWADHOC)
  ROLE        - Role to use (default: DEVREL_MODELING_RL)
  RUN_SCHEMA  - Fully-qualified schema (default: DEVREL.CNANTASENAMAT_DEV)

Additional SPCS-injected env vars used here:
  SNOWFLAKE_HOST     - SPCS cluster host
  SNOWFLAKE_ACCOUNT  - Snowflake account identifier

Optional overrides:
  MODEL    - Model for generation (default: claude-opus-4-7)
  TIMEOUT  - Generation timeout seconds (default: 300)
"""
import os
import subprocess
import time

import snowflake.connector


# ---------------------------------------------------------------------------
# Connection helpers (mirrors aeo_spcs_runner.py)
# ---------------------------------------------------------------------------

def get_connection():
    """Connect via SPCS OAuth token (inside container) or a named local connection."""
    token_path = "/snowflake/session/token"
    if os.path.exists(token_path):
        with open(token_path, "r") as f:
            token = f.read().strip()
        conn = snowflake.connector.connect(
            host=os.environ["SNOWFLAKE_HOST"],
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            token=token,
            authenticator="oauth",
        )
        return conn, token
    # Local dev fallback
    connection = os.environ.get("CONNECTION", "my-snowflake")
    return snowflake.connector.connect(connection_name=connection), None


def setup_cortex_connection_for_spcs(token, account, host, warehouse, role):
    """Write ~/.snowflake/connections.toml with the SPCS OAuth token so the
    Cortex CLI can authenticate and access its Snowflake tools (sql_execute,
    web_search, etc.).  Returns the connection name to pass to cortex -c."""
    config_dir = os.path.expanduser("~/.snowflake")
    os.makedirs(config_dir, exist_ok=True)
    connections_toml = (
        f"[spcs]\n"
        f'account = "{account}"\n'
        f'host = "{host}"\n'
        f'authenticator = "oauth"\n'
        f'token = "{token}"\n'
        f'warehouse = "{warehouse}"\n'
        f'role = "{role}"\n'
    )
    with open(os.path.join(config_dir, "connections.toml"), "w") as f:
        f.write(connections_toml)
    return "spcs"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_via_cortex_cli(prompt, model, connection, timeout=300):
    """Invoke the Cortex CLI in headless -p mode with all tools auto-approved.

    The -p flag is required for non-TTY subprocess execution. Without it,
    CoCo's underlying Ink (React terminal UI) library crashes with
    'Raw mode is not supported on the current process.stdin'.

    --dangerously-allow-all-tool-calls auto-approves every tool call so that
    web_search and web_fetch are not silently skipped in headless mode (where
    CoCo cannot interactively prompt for permission).

    Returns the response text string.
    """
    result = subprocess.run(
        ["cortex", "-c", connection, "-m", model, "-p", prompt,
         "--dangerously-allow-all-tool-calls"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"cortex CLI exited with code {result.returncode}: "
            f"{result.stderr[:500]}"
        )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    request_id = os.environ.get("REQUEST_ID", "")
    warehouse   = os.environ.get("WAREHOUSE", "SNOWADHOC")
    role        = os.environ.get("ROLE", "DEVREL_MODELING_RL")
    schema      = os.environ.get("RUN_SCHEMA", "DEVREL.CNANTASENAMAT_DEV")
    model       = os.environ.get("MODEL", "claude-opus-4-7")
    timeout     = int(os.environ.get("TIMEOUT", "300"))

    if not request_id:
        raise ValueError("REQUEST_ID environment variable is required")

    print(f"AEO Interactive Runner | request_id={request_id} | model={model}")

    t_start = time.time()

    # Connect to Snowflake
    conn, spcs_token = get_connection()
    cur = conn.cursor()
    if role:
        cur.execute(f"USE ROLE {role}")
    cur.execute(f"USE WAREHOUSE {warehouse}")
    print(f"Connected in {time.time() - t_start:.2f}s")

    # Setup Cortex CLI connection (critical: without this CoCo has no
    # Snowflake auth and will respond with 'restricted session' message)
    cc_connection = None
    if spcs_token:
        account = os.environ.get("SNOWFLAKE_ACCOUNT", "")
        host    = os.environ.get("SNOWFLAKE_HOST", "")
        cc_connection = setup_cortex_connection_for_spcs(
            spcs_token, account, host, warehouse, role
        )
        print(f"Cortex CLI connection configured: {cc_connection}")
    else:
        cc_connection = os.environ.get("CONNECTION", "my-snowflake")
        print(f"Cortex CLI connection (local): {cc_connection}")

    # Read the prompt from AEO_INTERACTIVE_RESULTS
    cur.execute(
        f"SELECT PROMPT FROM {schema}.AEO_INTERACTIVE_RESULTS "
        f"WHERE REQUEST_ID = %s LIMIT 1",
        (request_id,),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError(
            f"No row found in AEO_INTERACTIVE_RESULTS for REQUEST_ID={request_id}"
        )
    prompt = row[0]
    print(f"Prompt ({len(prompt)} chars): {prompt[:120]}...")

    # Mark as running
    cur.execute(
        f"UPDATE {schema}.AEO_INTERACTIVE_RESULTS "
        f"SET STATUS = 'running', UPDATED_AT = CURRENT_TIMESTAMP() "
        f"WHERE REQUEST_ID = %s",
        (request_id,),
    )

    # Generate
    t_gen = time.time()
    try:
        response_text = generate_via_cortex_cli(
            prompt, model=model, connection=cc_connection, timeout=timeout
        )
        gen_secs = time.time() - t_gen
        print(f"Generated {len(response_text)} chars in {gen_secs:.1f}s")

        cur.execute(
            f"UPDATE {schema}.AEO_INTERACTIVE_RESULTS "
            f"SET STATUS = 'complete', "
            f"    RESPONSE_TEXT = %s, "
            f"    COMPLETED_AT = CURRENT_TIMESTAMP() "
            f"WHERE REQUEST_ID = %s",
            (response_text, request_id),
        )
        print(f"Result written | total={time.time() - t_start:.1f}s")

    except Exception as e:
        err_msg = str(e)[:2000]
        print(f"GENERATION FAILED: {err_msg}")
        cur.execute(
            f"UPDATE {schema}.AEO_INTERACTIVE_RESULTS "
            f"SET STATUS = 'error', "
            f"    RESPONSE_TEXT = %s, "
            f"    COMPLETED_AT = CURRENT_TIMESTAMP() "
            f"WHERE REQUEST_ID = %s",
            (f"ERROR: {err_msg}", request_id),
        )

    conn.close()


if __name__ == "__main__":
    main()
