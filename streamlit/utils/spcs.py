"""SPCS integration helper for the AEO Streamlit app.

Used when the app is deployed on SiS and the native Cortex Code CLI binary
is not available. Delegates job launch to the AEO_TRIGGER_INTERACTIVE stored
procedure, then polls AEO_INTERACTIVE_RESULTS until the SPCS container writes
back its response.

SP contract:
  CALL AEO_TRIGGER_INTERACTIVE(prompt, warehouse, role, run_schema)
  Returns REQUEST_ID (VARCHAR) — the row key to poll.
"""

import time

SPCS_POLL_INTERVAL = 3    # seconds between status checks
SPCS_TIMEOUT       = 300  # 5 minutes — covers cold-start + execution


def run_via_spcs(
    session,
    prompt: str,
    run_schema: str,
    warehouse: str,
    role: str,
) -> str:
    """Trigger an SPCS job to run native Cortex Code CLI on a single prompt.

    Calls AEO_TRIGGER_INTERACTIVE to insert a pending row, fire the job
    service, and return the REQUEST_ID.  Polls AEO_INTERACTIVE_RESULTS
    until the container writes back a response, then returns that text.

    Args:
        session:    Active Snowpark session (SiS get_active_session()).
        prompt:     Full prompt text (may include system context + question).
        run_schema: Fully-qualified schema, e.g. "DEVREL.CNANTASENAMAT_DEV".
        warehouse:  Warehouse name for the SPCS container to use.
        role:       Role for the SPCS container to USE (e.g. DEVREL_INGEST_RL).

    Returns:
        Response text from the Cortex Code CLI, or an error string prefixed
        with "[Error: ..." if the job failed or timed out.
    """
    # SP handles: UUID generation, INSERT, EXECUTE JOB SERVICE
    rows = session.sql(
        f"CALL {run_schema}.AEO_TRIGGER_INTERACTIVE(?, ?, ?, ?)",
        params=[prompt, warehouse, role, run_schema],
    ).collect()
    request_id = rows[0][0]

    # Poll until the SPCS container writes back status=complete|error
    deadline = time.time() + SPCS_TIMEOUT
    while time.time() < deadline:
        result = session.sql(
            f"SELECT STATUS, RESPONSE_TEXT "
            f"FROM {run_schema}.AEO_INTERACTIVE_RESULTS "
            f"WHERE REQUEST_ID = ?",
            params=[request_id],
        ).collect()
        if result:
            status = result[0]["STATUS"]
            if status in ("complete", "error"):
                return result[0]["RESPONSE_TEXT"] or f"[{status}: empty response]"
        time.sleep(SPCS_POLL_INTERVAL)

    return "[Error: SPCS job timed out after 5 minutes]"
