"""Page 5 — Questions Explorer: drilldown by run, category, and question type."""
import re
import json
import uuid
import streamlit as st
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import run_query, run_write, config_label, get_current_username, DB, SCH, ENV
from utils.db import v3_per_question_sql
from utils.ui import model_selector

ADMIN_USERS = {"cnantasenamat", "chaninn"}
current_user = get_current_username()

st.title(":material/manage_search: Questions Explorer")
st.caption("Per-question scores for every configuration — filter by config, category, or question type to drill down into individual results.")

# ── Model selector (DevRel only) ──────────────────────────────────────────────
if ENV == "devrel":
    _label, _model = model_selector("qe_model_sel")

# --- Load data ---
if ENV == "devrel":
    pq = run_query(v3_per_question_sql(_model))
    pq["Config"] = pq.apply(
        lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
    )
    q_meta = run_query(
        "SELECT QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE FROM AEO_QUESTIONS"
    )
    df = pq.merge(q_meta, on="QUESTION_ID", how="left")
else:
    df = run_query("""
        SELECT q.QUESTION_ID, q.QUESTION_TEXT, q.CATEGORY, q.QUESTION_TYPE,
               h.RUN_ID, h.DOMAIN_PROMPT, h.CITATION, h.AGENTIC, h.SELF_CRITIQUE,
               rc.MODEL,
               h.TOTAL_SCORE, h.MUST_HAVE_PASS,
               h.CORRECTNESS, h.COMPLETENESS, h.RECENCY, h.CITATION_SCORE, h.RECOMMENDATION
        FROM V_AEO_PER_QUESTION_HEATMAP h
        JOIN AEO_QUESTIONS q   ON h.QUESTION_ID = q.QUESTION_ID
        JOIN (SELECT DISTINCT RUN_ID, MODEL FROM AEO_RUN_CONFIG) rc ON h.RUN_ID = rc.RUN_ID
        ORDER BY h.RUN_ID, q.QUESTION_ID
    """)
    df["Config"] = df.apply(
        lambda r: config_label(r.DOMAIN_PROMPT, r.CITATION, r.AGENTIC, r.SELF_CRITIQUE), axis=1
    )

df["Score %"] = (df["TOTAL_SCORE"] / 50.0 * 100).round(1)

all_configs = sorted(df["Config"].unique())
all_cats    = sorted(df["CATEGORY"].unique())
all_types   = sorted(df["QUESTION_TYPE"].unique())

# --- Per-question table ---
st.subheader(":material/table_rows: Question-level results")
fcol1, fcol2, fcol3 = st.columns(3)
default_cfg = next((v for v in all_configs if v == "C+A"), all_configs[0])
sel_config  = fcol1.selectbox("Configuration", all_configs, index=all_configs.index(default_cfg))
sel_cats    = fcol2.selectbox("Category",      ["All"] + all_cats)
sel_types   = fcol3.selectbox("Question Type", ["All"] + all_types)

mask = (df["Config"] == sel_config)
if sel_cats  != "All":
    mask &= df["CATEGORY"]      == sel_cats
if sel_types != "All":
    mask &= df["QUESTION_TYPE"] == sel_types
filtered = df[mask].copy()

if filtered.empty:
    st.warning("No data matches the current filters.")
    st.stop()
DIMS = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]

show = filtered[
    ["QUESTION_ID", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
     "Config", "Score %", "MUST_HAVE_PASS"] + DIMS
].rename(columns={
    "QUESTION_ID":   "Q#",
    "QUESTION_TEXT": "Question",
    "CATEGORY":      "Category",
    "QUESTION_TYPE": "Type",
    "MUST_HAVE_PASS":"MH Pass",
    "CORRECTNESS":   "Correctness",
    "COMPLETENESS":  "Completeness",
    "RECENCY":       "Recency",
    "CITATION_SCORE":"Citation",
    "RECOMMENDATION":"Recommendation",
}).copy()

show["MH Pass"] = show["MH Pass"].apply(lambda x: "Pass" if x == 1 else "Fail")

st.dataframe(
    show,
    column_config={
        "Category": st.column_config.TextColumn("Category"),
        "Config": st.column_config.TextColumn("Config"),
        "Type": st.column_config.TextColumn("Type"),
        "MH Pass": st.column_config.TextColumn("MH Pass"),
        "Score %": st.column_config.ProgressColumn(
            "Score %",
            format="%.1f%%",
            min_value=0,
            max_value=100,
        ),
        "Correctness": st.column_config.ProgressColumn(
            "Correctness", format="%.1f", min_value=0, max_value=10,
        ),
        "Completeness": st.column_config.ProgressColumn(
            "Completeness", format="%.1f", min_value=0, max_value=10,
        ),
        "Recency": st.column_config.ProgressColumn(
            "Recency", format="%.1f", min_value=0, max_value=10,
        ),
        "Citation": st.column_config.ProgressColumn(
            "Citation", format="%.1f", min_value=0, max_value=10,
        ),
        "Recommendation": st.column_config.ProgressColumn(
            "Recommendation", format="%.1f", min_value=0, max_value=10,
        ),
    },
    use_container_width=True,
    height=500,
)

with st.expander(":material/chat: View generated answer"):
    q_ids    = sorted(filtered["QUESTION_ID"].unique())
    sel_view = st.selectbox("Select a question", q_ids, key="view_answer_q")

    q_text = filtered[filtered["QUESTION_ID"] == sel_view].iloc[0]["QUESTION_TEXT"]
    st.markdown(f"**{sel_view}:** {q_text}")

    if ENV == "devrel":
        # In V3, the response is embedded in TRANSCRIPT_JSONL
        run_id_str = str(filtered["RUN_ID"].iloc[0])
        tran_df = run_query(
            f"SELECT TRANSCRIPT_JSONL FROM V3_AEO_TRANSCRIPT "
            f"WHERE RUN_ID = '{run_id_str}' AND QUESTION_ID = '{sel_view}'"
        )
        if not tran_df.empty and tran_df.iloc[0]["TRANSCRIPT_JSONL"]:
            jsonl = tran_df.iloc[0]["TRANSCRIPT_JSONL"]
            # Extract the last assistant message text from JSONL
            response_text = None
            try:
                lines = [l for l in jsonl.split("\n") if l.strip()]
                for line in reversed(lines):
                    try:
                        msg = json.loads(line)
                        if msg.get("role") == "assistant":
                            for block in msg.get("content", []):
                                if isinstance(block, dict) and block.get("type") == "text":
                                    response_text = block["text"]
                                    break
                            if response_text:
                                break
                    except json.JSONDecodeError:
                        continue
            except Exception:
                pass
            if response_text:
                st.markdown(response_text)
            else:
                st.caption("Response text could not be extracted from transcript.")
        else:
            st.caption("No transcript found for this question and configuration.")
    else:
        run_id = int(filtered["RUN_ID"].iloc[0])
        resp_df = run_query(
            f"SELECT RESPONSE_TEXT FROM AEO_RESPONSES "
            f"WHERE RUN_ID = {run_id} AND QUESTION_ID = '{sel_view}'"
        )
        if not resp_df.empty and resp_df.iloc[0]["RESPONSE_TEXT"]:
            st.markdown(resp_df.iloc[0]["RESPONSE_TEXT"])
        else:
            st.caption("No response found for this question and configuration.")

with st.expander(":material/key: Configuration key"):
    st.markdown("""
**Configuration acronyms** — each letter represents a feature that was enabled for that run:

| Letter | Feature | Description |
|--------|---------|-------------|
| **D** | Domain Prompt | A system prompt that frames the agent as a Snowflake expert |
| **C** | Citation | The agent is instructed to cite sources in its response |
| **A** | Agentic | The agent has access to tools (e.g. search, retrieval) |
| **S** | Self-Critique | The agent reviews and revises its own answer before returning it |
| **Baseline** | None | No features enabled — raw model response only |

Combinations like **C+A** mean Citation and Agentic were both enabled. **D+C+A+S** means all four features were on.
""")


# =============================================================================
# Submit a question to the benchmark
# =============================================================================
st.divider()
with st.form("submit_question", clear_on_submit=True):
    st.subheader(":material/add_circle: Submit a question to the benchmark")
    st.caption("Questions are reviewed by the admin before being added to the official benchmark set.")
    sub_question = st.text_area(
        "Question *",
        height=80,
        placeholder="e.g. How do I create a Cortex Search service?",
    )
    sub_col1, sub_col2 = st.columns(2)
    sub_category = sub_col1.selectbox("Category", sorted(all_cats))
    sub_type     = sub_col2.selectbox("Question type", sorted(all_types))

    with st.expander("Canonical answer + Must-Haves (optional)"):
        sub_canonical = st.text_area("Canonical answer", height=80)
        mh_cols = st.columns(5)
        sub_mh = [
            mh_cols[i].text_input(f"Must-have {i+1}", key=f"sub_mh_{i}")
            for i in range(5)
        ]

    submitted = st.form_submit_button("Submit question", type="primary")

if submitted:
    if not sub_question.strip():
        st.error("Question text is required.")
    else:
        run_write(
            """INSERT INTO AEO_QUESTION_CANDIDATES
               (SUBMISSION_ID, SUBMITTED_BY, FIRST_NAME, LAST_NAME,
                QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
                CANONICAL_ANSWER, MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5)
               VALUES (?, CURRENT_USER(), NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            params=[
                str(uuid.uuid4()),
                sub_question.strip(), sub_category, sub_type,
                sub_canonical.strip() or None,
                sub_mh[0].strip() or None, sub_mh[1].strip() or None,
                sub_mh[2].strip() or None, sub_mh[3].strip() or None,
                sub_mh[4].strip() or None,
            ],
        )
        run_query.clear()
        st.success("Question submitted! The admin will review it before adding it to the benchmark.")
        st.rerun()

# --- Pending submissions table (visible to all) ---
public_pending_df = run_query(
    "SELECT SUBMITTED_AT, QUESTION_TEXT, CATEGORY, QUESTION_TYPE "
    "FROM AEO_QUESTION_CANDIDATES WHERE STATUS = 'pending' ORDER BY SUBMITTED_AT DESC"
)
if not public_pending_df.empty:
    with st.expander(f":material/pending: Pending Review ({len(public_pending_df)})"):
        st.caption(f"Saved to `{DB}.{SCH}.AEO_QUESTION_CANDIDATES`")
        st.dataframe(
            public_pending_df.rename(columns={
                "SUBMITTED_AT":  "Submitted",
                "QUESTION_TEXT": "Question",
                "CATEGORY":      "Category",
                "QUESTION_TYPE": "Type",
            }),
            column_config={
                "Submitted": st.column_config.DatetimeColumn("Submitted", format="YYYY-MM-DD HH:mm"),
                "Question":  st.column_config.TextColumn("Question",  width="large"),
            },
            use_container_width=True,
            hide_index=True,
        )

# =============================================================================
# Admin review — visible only to cnantasenamat / chaninn
# =============================================================================
if current_user in ADMIN_USERS:
    st.divider()
    with st.container(border=True):
        st.subheader(":material/admin_panel_settings: Benchmark Question Review")

        pending_df = run_query(
            "SELECT * FROM AEO_QUESTION_CANDIDATES WHERE STATUS = 'pending' ORDER BY SUBMITTED_AT"
        )

        tab_pending, tab_sets = st.tabs([
            f"Pending ({len(pending_df)})",
            "Benchmark Sets",
        ])

        with tab_pending:
            edited_df = None  # scoped for use in the benchmark section below

            st.subheader(":material/pending: Pending")
            st.caption("Tick questions in the table below to add them to a benchmark set.")
            if pending_df.empty:
                st.info("No pending submissions.")
            else:
                review_df = pending_df[[
                    "SUBMISSION_ID", "SUBMITTED_AT", "SUBMITTED_BY",
                    "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
                ]].copy()
                review_df.insert(0, "Approve", False)
                review_df.insert(1, "Delete", False)

                edited_df = st.data_editor(
                    review_df,
                    column_config={
                        "Approve":       st.column_config.CheckboxColumn("Approve", default=False, width="small"),
                        "Delete":        st.column_config.CheckboxColumn("Delete", default=False, width="small"),
                        "SUBMISSION_ID": None,
                        "SUBMITTED_AT":  st.column_config.DatetimeColumn("Submitted", format="YYYY-MM-DD HH:mm"),
                        "SUBMITTED_BY":  st.column_config.TextColumn("By"),
                        "QUESTION_TEXT": st.column_config.TextColumn("Question", width="large"),
                        "CATEGORY":      st.column_config.TextColumn("Category"),
                        "QUESTION_TYPE": st.column_config.TextColumn("Type"),
                    },
                    disabled=["SUBMISSION_ID", "SUBMITTED_AT", "SUBMITTED_BY", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE"],
                    hide_index=True,
                    use_container_width=True,
                    key="pending_review_table",
                )

                to_delete = edited_df[edited_df["Delete"]]
                if st.button("Delete selected", key="pending_delete", disabled=to_delete.empty):
                    for _, drow in to_delete.iterrows():
                        run_write(
                            "DELETE FROM AEO_QUESTION_CANDIDATES WHERE SUBMISSION_ID = ?",
                            params=[drow["SUBMISSION_ID"]],
                        )
                    run_query.clear()
                    st.rerun()


            checked = edited_df[edited_df["Approve"]] if edited_df is not None else None
            st.caption(
                f"{len(checked)} question(s) selected." if checked is not None and not checked.empty
                else "After ticking on questions, select a benchmark set to add to."
            )

            existing_bm_df = run_query(
                f"SELECT TABLE_NAME FROM {DB}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{SCH}' AND TABLE_NAME LIKE 'AEO_BENCHMARK_%' "
                f"ORDER BY TABLE_NAME"
            )
            existing_names = existing_bm_df["TABLE_NAME"].tolist() if not existing_bm_df.empty else []

            if existing_names:
                bm_options = ["— select a benchmark set —"] + existing_names + ["+ Create new..."]
            else:
                bm_options = ["+ Create new..."]

            bm_choice = st.selectbox(
                "Benchmark set",
                options=bm_options,
                format_func=lambda x: x.replace("AEO_BENCHMARK_", "").lower()
                    if x not in ("— select a benchmark set —", "+ Create new...") else x,
                key="bm_choice",
            )

            tbl           = None
            bm_name_input = ""
            if bm_choice == "— select a benchmark set —":
                pass
            elif bm_choice == "+ Create new...":
                bm_name_input = st.text_input(
                    "New benchmark set name",
                    placeholder="e.g. snowflake_core_v2",
                    help="Table will be named AEO_BENCHMARK_<name>.",
                    key="bm_new_name",
                )
                safe = re.sub(r"[^A-Z0-9_]", "_", bm_name_input.strip().upper()) if bm_name_input.strip() else ""
                tbl  = f"{DB}.{SCH}.AEO_BENCHMARK_{safe}" if safe else None
            else:
                bm_name_input = bm_choice
                tbl = f"{DB}.{SCH}.{bm_choice}"

            if st.button("Submit", type="primary", key="bm_submit"):
                if checked is None or checked.empty:
                    st.error("Please tick at least one question in the table above.")
                elif bm_choice == "— select a benchmark set —":
                    st.error("Please select a benchmark set.")
                elif bm_choice == "+ Create new..." and not bm_name_input.strip():
                    st.error("Please enter a benchmark set name.")
                elif tbl is None:
                    st.error("Please enter a valid benchmark set name.")
                else:
                    run_write(f"""
                        CREATE TABLE IF NOT EXISTS {tbl} (
                            SET_NAME      VARCHAR,
                            QUESTION_TEXT VARCHAR,
                            CATEGORY      VARCHAR,
                            QUESTION_TYPE VARCHAR,
                            ADDED_AT      TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                            ADDED_BY      VARCHAR   DEFAULT CURRENT_USER()
                        )
                    """)
                    set_label = bm_name_input.strip() if bm_choice == "+ Create new..." else bm_choice

                    existing_q_df = run_query(f"SELECT QUESTION_TEXT FROM {tbl}")
                    existing_qs   = set(existing_q_df["QUESTION_TEXT"].tolist()) if not existing_q_df.empty else set()
                    new_rows  = checked[~checked["QUESTION_TEXT"].isin(existing_qs)]
                    dupe_rows = checked[checked["QUESTION_TEXT"].isin(existing_qs)]

                    if new_rows.empty:
                        st.error(
                            f"All {len(dupe_rows)} selected question(s) already exist "
                            f"in **{set_label}**. Nothing was added."
                        )
                    else:
                        if not dupe_rows.empty:
                            st.warning(
                                f"{len(dupe_rows)} question(s) already in this set "
                                f"and were skipped: "
                                + ", ".join(f'"{q[:60]}"' for q in dupe_rows["QUESTION_TEXT"].tolist())
                            )
                        for _, qrow in new_rows.iterrows():
                            run_write(
                                f"INSERT INTO {tbl} "
                                f"(SET_NAME, QUESTION_TEXT, CATEGORY, QUESTION_TYPE, ADDED_AT, ADDED_BY) "
                                f"VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP(), CURRENT_USER())",
                                params=[set_label, qrow["QUESTION_TEXT"], qrow["CATEGORY"], qrow["QUESTION_TYPE"]],
                            )
                            run_write(
                                """UPDATE AEO_QUESTION_CANDIDATES
                                   SET STATUS = 'approved',
                                       REVIEWED_AT = CURRENT_TIMESTAMP(),
                                       REVIEWED_BY = ?
                                   WHERE SUBMISSION_ID = ?""",
                                params=[current_user, qrow["SUBMISSION_ID"]],
                            )
                        run_query.clear()
                        st.success(f"Added {len(new_rows)} question(s) to `{tbl}`.")
                        st.rerun()

        with tab_sets:
            st.subheader(":material/dataset: Benchmark Sets")
            sets_df = run_query(
                f"SELECT TABLE_NAME FROM {DB}.INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{SCH}' AND TABLE_NAME LIKE 'AEO_BENCHMARK_%' "
                f"ORDER BY TABLE_NAME"
            )
            if sets_df.empty:
                st.info("No benchmark sets found. Create one from the Pending tab.")
            else:
                set_names = sets_df["TABLE_NAME"].tolist()
                selected_set = st.selectbox(
                    "Benchmark set",
                    options=set_names,
                    format_func=lambda x: x.replace("AEO_BENCHMARK_", "").lower(),
                    key="view_bm_set",
                )
                if selected_set:
                    set_questions_df = run_query(
                        f"SELECT QUESTION_TEXT, CATEGORY, QUESTION_TYPE, SET_NAME, ADDED_AT, ADDED_BY "
                        f"FROM {DB}.{SCH}.{selected_set} "
                        f"QUALIFY ROW_NUMBER() OVER (PARTITION BY QUESTION_TEXT ORDER BY ADDED_AT) = 1 "
                        f"ORDER BY ADDED_AT"
                    )
                    st.caption(f"`{DB}.{SCH}.{selected_set}` · {len(set_questions_df)} question(s)")
                    if set_questions_df.empty:
                        st.info("This benchmark set has no questions yet.")
                    else:
                        delete_df = set_questions_df.copy()
                        delete_df.insert(0, "Delete", False)
                        edited_set_df = st.data_editor(
                            delete_df.rename(columns={
                                "QUESTION_TEXT": "Question",
                                "CATEGORY":      "Category",
                                "QUESTION_TYPE": "Type",
                                "SET_NAME":      "Set",
                                "ADDED_AT":      "Added",
                                "ADDED_BY":      "By",
                            }),
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Delete":   st.column_config.CheckboxColumn("Delete", default=False, width="small"),
                                "Question": st.column_config.TextColumn("Question", width="large"),
                                "Added":    st.column_config.DatetimeColumn("Added", format="YYYY-MM-DD HH:mm"),
                            },
                            disabled=["Question", "Category", "Type", "Set", "Added", "By"],
                            key="set_delete_table",
                        )
                        to_delete = edited_set_df[edited_set_df["Delete"]]
                        if st.button("Delete selected", type="primary", key="delete_set_rows"):
                            if to_delete.empty:
                                st.error("Tick at least one row to delete.")
                            else:
                                for _, drow in to_delete.iterrows():
                                    run_write(
                                        f"DELETE FROM {DB}.{SCH}.{selected_set} WHERE QUESTION_TEXT = ?",
                                        params=[drow["Question"]],
                                    )
                                run_query.clear()
                                st.success(f"Deleted {len(to_delete)} question(s) from `{DB}.{SCH}.{selected_set}`.")
                                st.rerun()
