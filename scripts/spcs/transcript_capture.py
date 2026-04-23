"""
transcript_capture.py — Capture and parse Cortex Code CLI session transcripts
for AEO benchmark eval runs.

Per the Anthropic "Demystifying evals for AI agents" article, a transcript is
the complete record of a trial: outputs, tool calls, reasoning, intermediate
results, and usage metadata.  For Cortex Code CLI (`cortex -p`) runs, that
record lives in ~/.snowflake/cortex/conversations/<session_id>.history.jsonl.

Public API
----------
  capture_cli_transcript(t_before)              → dict  (always safe; returns {} on failure)
  fetch_cli_tokens(cur, t_before, t_after, model) → dict  (always safe; returns {} on failure)
  find_latest_session(t_before)                 → str | None
  parse_session_jsonl(path)                     → dict

capture_cli_transcript() returned dict shape (all keys present, values may be None/0/[]):
  n_turns          int   – assistant turns in the session
  n_tool_calls     int   – total tool-use blocks across all turns
  tool_calls       list  – tool names in call order, e.g. ["bash", "web_fetch"]
  tool_call_counts dict  – {"bash": 3, "web_fetch": 1, ...}
  n_thinking_blocks int  – extended-thinking blocks
  transcript_jsonl str   – raw JSONL text, truncated to MAX_JSONL_CHARS

fetch_cli_tokens() returned dict shape:
  prompt_tokens     int  – input + cache_read_input + cache_write_input (all turns summed)
  completion_tokens int  – output tokens (all turns summed)
  (shape matches cortex_complete usage dict so insert_response() handles both paths alike)

Usage in aeo_spcs_runner.py
---------------------------
  t_before = time.time()
  result = subprocess.run(["cortex", "-c", conn, "-m", model, "-p", prompt], ...)
  t_after = time.time()
  transcript = capture_cli_transcript(t_before)
  tokens    = fetch_cli_tokens(cur, t_before, t_after, model)
  # pass transcript= and usage=tokens to insert_response()
"""

import glob
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone

# Where Cortex Code writes session files
CONVERSATIONS_DIR = os.path.expanduser("~/.snowflake/cortex/conversations")

# Truncation limit matches the VARCHAR(65000) column on AEO_RESPONSES
MAX_JSONL_CHARS = 65000

# Small sleep after subprocess returns before scanning for the new file;
# the CLI may still be flushing the JSONL to disk.
POST_RUN_SETTLE_SECS = 0.5

# Delay before querying CORTEX_CODE_CLI_USAGE_HISTORY to allow the view
# to materialise the rows for the just-completed cortex -p session.
FETCH_TOKENS_DELAY_SECS = 5

# Allowlist pattern for model names used in Snowflake JSON path expressions.
# Prevents injection via the model name parameter in fetch_cli_tokens().
_MODEL_NAME_RE = re.compile(r'^[\w][\w\-\.]*$')


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def capture_cli_transcript(t_before: float) -> dict:
    """Find and parse the session JSONL created after t_before.

    Always returns a dict (never raises).  Returns {} when no JSONL is found
    (e.g. inside an SPCS container where the conversations dir does not exist,
    or when cortex -p does not persist a session file).
    """
    try:
        time.sleep(POST_RUN_SETTLE_SECS)
        path = find_latest_session(t_before)
        if path is None:
            return {}
        return parse_session_jsonl(path)
    except Exception as exc:
        print(f"  [transcript] capture failed (non-fatal): {exc}")
        return {}


# ---------------------------------------------------------------------------
# Token fetch from CORTEX_CODE_CLI_USAGE_HISTORY
# ---------------------------------------------------------------------------

def fetch_cli_tokens(cur, t_before: float, t_after: float, model: str) -> dict:
    """Query CORTEX_CODE_CLI_USAGE_HISTORY for token counts in [t_before, t_after].

    Sums all API turns made by CURRENT_USER() during the window that contain
    entries for the given model key in TOKENS_GRANULAR.  This captures every
    turn of the cortex -p session (tool calls + final answer).

    Token accounting:
      prompt_tokens     = input + cache_read_input + cache_write_input  (per turn, summed)
      completion_tokens = output  (per turn, summed)

    The returned dict shape matches the cortex_complete usage dict so
    insert_response() stores tokens identically for both generation modes.

    Always returns a dict (never raises).  Returns {} when the query fails
    or returns no rows — token columns remain NULL in that case.

    Note: CORTEX_CODE_CLI_USAGE_HISTORY is near-real-time; FETCH_TOKENS_DELAY_SECS
    is a precautionary sleep to let the view materialise before querying.
    """
    try:
        if not _MODEL_NAME_RE.match(model):
            raise ValueError(f"Invalid model name for token fetch: {model!r}")

        time.sleep(FETCH_TOKENS_DELAY_SECS)

        fmt = "%Y-%m-%d %H:%M:%S.%f +0000"
        t_before_str = datetime.fromtimestamp(t_before, tz=timezone.utc).strftime(fmt)
        t_after_str  = datetime.fromtimestamp(t_after,  tz=timezone.utc).strftime(fmt)

        sql = f"""
            SELECT
                SUM(
                    COALESCE(TOKENS_GRANULAR:"{model}":input::INTEGER, 0) +
                    COALESCE(TOKENS_GRANULAR:"{model}":cache_read_input::INTEGER, 0) +
                    COALESCE(TOKENS_GRANULAR:"{model}":cache_write_input::INTEGER, 0)
                ) AS prompt_tokens,
                SUM(
                    COALESCE(TOKENS_GRANULAR:"{model}":output::INTEGER, 0)
                ) AS completion_tokens,
                SUM(
                    COALESCE(TOKENS_GRANULAR:"{model}":cache_read_input::INTEGER, 0)
                ) AS cache_read_tokens,
                SUM(
                    COALESCE(TOKENS_GRANULAR:"{model}":cache_write_input::INTEGER, 0)
                ) AS cache_write_tokens,
                MIN_BY(REQUEST_ID, USAGE_TIME) AS first_request_id,
                MAX_BY(REQUEST_ID, USAGE_TIME) AS last_request_id
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_CODE_CLI_USAGE_HISTORY
            WHERE USER_NAME = CURRENT_USER()
              AND USAGE_TIME >= %s::TIMESTAMP_TZ
              AND USAGE_TIME <= %s::TIMESTAMP_TZ
              AND TOKENS_GRANULAR:"{model}" IS NOT NULL
        """
        cur.execute(sql, (t_before_str, t_after_str))
        row = cur.fetchone()
        if row is None or (row[0] is None and row[1] is None):
            print("  [tokens] no rows found in usage history for this window")
            return {}
        result = {
            "prompt_tokens":     int(row[0] or 0),
            "completion_tokens": int(row[1] or 0),
            "cache_read_tokens": int(row[2] or 0),
            "cache_write_tokens": int(row[3] or 0),
            "first_request_id":  row[4],
            "last_request_id":   row[5],
        }
        print(f"  [tokens] prompt={result['prompt_tokens']} completion={result['completion_tokens']}"
              f" cache_read={result['cache_read_tokens']} cache_write={result['cache_write_tokens']}")
        return result
    except Exception as exc:
        print(f"  [tokens] fetch failed (non-fatal): {exc}")
        return {}


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_latest_session(t_before: float) -> "str | None":
    """Return the path of the .history.jsonl written after t_before, or None.

    When multiple files qualify (e.g. parallel batches), returns the most
    recently modified one — callers should ensure only one cortex -p process
    runs at a time per batch worker.
    """
    if not os.path.isdir(CONVERSATIONS_DIR):
        return None
    pattern = os.path.join(CONVERSATIONS_DIR, "*.history.jsonl")
    candidates = [
        f for f in glob.glob(pattern)
        if os.path.getmtime(f) > t_before
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


# ---------------------------------------------------------------------------
# JSONL parsing
# ---------------------------------------------------------------------------

def parse_session_jsonl(path: str) -> dict:
    """Parse a Cortex Code .history.jsonl file into structured transcript metrics.

    JSONL event shape (relevant fields):
      {"role": "assistant", "content": [
          {"type": "thinking", "thinking": "..."},
          {"type": "tool_use", "tool_use": {"name": "bash", "input": {...}}},
          {"type": "text",     "text": "..."}
      ]}

    Note the double-nesting: tool_use details live at item["tool_use"]["name"],
    not at item["name"].
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()

    n_turns = 0
    tool_calls: list[str] = []
    n_thinking = 0

    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue

        role = event.get("role")
        content = event.get("content")
        if not isinstance(content, list):
            continue

        if role == "assistant":
            n_turns += 1

        for item in content:
            item_type = item.get("type")
            if item_type == "tool_use":
                nested = item.get("tool_use", {})
                tool_calls.append(nested.get("name", "unknown"))
            elif item_type == "thinking":
                n_thinking += 1

    raw_jsonl = "".join(lines)
    return {
        "n_turns": n_turns,
        "n_tool_calls": len(tool_calls),
        "tool_calls": tool_calls,
        "tool_call_counts": dict(Counter(tool_calls)),
        "n_thinking_blocks": n_thinking,
        "transcript_jsonl": raw_jsonl[:MAX_JSONL_CHARS],
    }


# ---------------------------------------------------------------------------
# Standalone verification test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """Run this directly to verify that `cortex -p` creates a session JSONL file.

    Usage:
        cd /Users/cnantasenamat/Documents/Coco/aeo/dev/spcs
        python3 transcript_capture.py

    Expected output:
        - A session JSONL file is found after the cortex run
        - Transcript metrics are printed (n_turns >= 1, n_tool_calls >= 0)
        - If JSONL is NOT found, the key assumption is invalid and the runner
          should fall back to stdout-only capture.
    """
    import subprocess

    CONNECTION = os.environ.get("CONNECTION", "my-snowflake")
    TEST_PROMPT = "In one sentence, what is Snowflake Cortex Search?"

    print("=" * 60)
    print("AEO Transcript Capture — Verification Test")
    print(f"Connection : {CONNECTION}")
    print(f"Prompt     : {TEST_PROMPT}")
    print("=" * 60)

    # Snapshot conversations dir before run
    before_files = set(glob.glob(os.path.join(CONVERSATIONS_DIR, "*.history.jsonl")))
    print(f"\nExisting JSONL files: {len(before_files)}")

    t_before = time.time()
    print(f"\nRunning: cortex -c {CONNECTION} -p '<prompt>' ...")

    proc = subprocess.run(
        ["cortex", "-c", CONNECTION, "-p", TEST_PROMPT],
        capture_output=True,
        text=True,
        timeout=120,
    )

    print(f"Return code : {proc.returncode}")
    print(f"Stdout      : {proc.stdout.strip()[:200]}")
    if proc.stderr.strip():
        print(f"Stderr      : {proc.stderr.strip()[:200]}")

    time.sleep(POST_RUN_SETTLE_SECS)

    after_files = set(glob.glob(os.path.join(CONVERSATIONS_DIR, "*.history.jsonl")))
    new_files = after_files - before_files
    print(f"\nNew JSONL files created: {len(new_files)}")

    if new_files:
        path = max(new_files, key=os.path.getmtime)
        print(f"File: {os.path.basename(path)}")
        metrics = parse_session_jsonl(path)
        print("\nTranscript metrics:")
        for k, v in metrics.items():
            if k == "transcript_jsonl":
                print(f"  transcript_jsonl : {len(v)} chars")
            elif k == "tool_calls":
                print(f"  tool_calls       : {v}")
            else:
                print(f"  {k:<20} : {v}")
        print("\n[PASS] cortex -p creates a JSONL file. Transcript capture works.")
    else:
        # Check by mtime instead (file may have been created before snapshot)
        path = find_latest_session(t_before)
        if path:
            print(f"File found by mtime: {os.path.basename(path)}")
            metrics = parse_session_jsonl(path)
            print(f"  n_turns: {metrics['n_turns']}, n_tool_calls: {metrics['n_tool_calls']}")
            print("\n[PASS] JSONL found by mtime. Transcript capture works.")
        else:
            print("\n[FAIL] No JSONL file found after cortex -p run.")
            print("Transcript columns will be NULL for all cortex_cli runs.")
            print("Consider using stdout-only metrics or a different capture strategy.")
