"""Doc Eval Candidates — review scored doc-page submissions and promote to benchmark."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from utils.db import run_query, run_write, get_current_username, DB, SCH

ADMIN_USERS = {"cnantasenamat", "chaninn"}
current_user = get_current_username()

st.title(":material/rate_review: Doc Eval Candidates")
st.caption(
    "Scored doc-page submissions from the AEO Doc Eval skill. "
    "Admins can promote approved candidates into the benchmark question bank."
)

# ---------------------------------------------------------------------------
# Graceful fallback if setup script hasn't been run yet
# ---------------------------------------------------------------------------
try:
    raw = run_query(
        "SELECT * FROM AEO_DOC_CANDIDATES ORDER BY SUBMITTED_AT DESC"
    )
except Exception as e:
    if "does not exist" in str(e).lower() or "not authorized" in str(e).lower():
        st.info(
            "The `AEO_DOC_CANDIDATES` table does not exist yet. "
            "Run `setup_product_manager_role.sql` as `DEVREL_ADMIN_RL` to create it."
        )
    else:
        st.error(f"Unexpected error loading candidates: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# KPI metrics
# ---------------------------------------------------------------------------
total      = len(raw)
pending    = int((raw["STATUS"] == "PENDING").sum())   if total else 0
approved   = int((raw["STATUS"] == "APPROVED").sum())  if total else 0
rejected   = int((raw["STATUS"] == "REJECTED").sum())  if total else 0
avg_score  = round(raw["SCORE_TOTAL"].mean() * 2, 1)   if total else 0.0   # /50 → %
avg_mh     = round(raw["MH_PASS_RATE"].mean() * 100, 1) if total else 0.0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total",    total)
c2.metric("Pending",  pending)
c3.metric("Approved", approved)
c4.metric("Rejected", rejected)
c5.metric("Avg Score %", f"{avg_score:.1f}%")
c6.metric("Avg MH Pass %", f"{avg_mh:.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Submissions table
# ---------------------------------------------------------------------------
st.subheader(":material/table_rows: All Submissions")

status_filter = st.selectbox(
    "Filter by status", ["All", "PENDING", "APPROVED", "REJECTED"], index=0
)

df = raw.copy() if status_filter == "All" else raw[raw["STATUS"] == status_filter].copy()

if df.empty:
    st.info("No submissions match the current filter.")
else:
    SCORE_DIMS = [
        "SCORE_CORRECTNESS", "SCORE_COMPLETENESS",
        "SCORE_RECENCY", "SCORE_CITATION", "SCORE_RECOMMENDATION",
    ]
    show_cols = [
        "CANDIDATE_ID", "STATUS", "SUBMITTED_AT", "SUBMITTED_BY",
        "DOC_URL", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
        "SCORE_TOTAL", "MH_PASS_RATE",
    ] + SCORE_DIMS + ["REVIEWED_BY", "REVIEWED_AT"]

    show = df[show_cols].rename(columns={
        "CANDIDATE_ID":        "ID",
        "STATUS":              "Status",
        "SUBMITTED_AT":        "Submitted",
        "SUBMITTED_BY":        "By",
        "DOC_URL":             "Doc URL",
        "QUESTION_TEXT":       "Question",
        "CATEGORY":            "Category",
        "QUESTION_TYPE":       "Type",
        "SCORE_TOTAL":         "Total (/50)",
        "MH_PASS_RATE":        "MH Pass",
        "SCORE_CORRECTNESS":   "Correctness",
        "SCORE_COMPLETENESS":  "Completeness",
        "SCORE_RECENCY":       "Recency",
        "SCORE_CITATION":      "Citation",
        "SCORE_RECOMMENDATION":"Recommendation",
        "REVIEWED_BY":         "Reviewed By",
        "REVIEWED_AT":         "Reviewed At",
    })

    st.dataframe(
        show,
        column_config={
            "Total (/50)": st.column_config.ProgressColumn(
                "Total (/50)", format="%.1f", min_value=0, max_value=50,
            ),
            "MH Pass": st.column_config.ProgressColumn(
                "MH Pass %", format="%.0f%%", min_value=0, max_value=1,
            ),
            "Correctness":    st.column_config.ProgressColumn("Correctness",    format="%.1f", min_value=0, max_value=10),
            "Completeness":   st.column_config.ProgressColumn("Completeness",   format="%.1f", min_value=0, max_value=10),
            "Recency":        st.column_config.ProgressColumn("Recency",        format="%.1f", min_value=0, max_value=10),
            "Citation":       st.column_config.ProgressColumn("Citation",       format="%.1f", min_value=0, max_value=10),
            "Recommendation": st.column_config.ProgressColumn("Recommendation", format="%.1f", min_value=0, max_value=10),
            "Submitted":      st.column_config.DatetimeColumn("Submitted",  format="YYYY-MM-DD HH:mm"),
            "Reviewed At":    st.column_config.DatetimeColumn("Reviewed At", format="YYYY-MM-DD HH:mm"),
            "Question":       st.column_config.TextColumn("Question",  width="large"),
            "Doc URL":        st.column_config.LinkColumn("Doc URL"),
        },
        use_container_width=True,
        hide_index=True,
        height=480,
    )

# ---------------------------------------------------------------------------
# Admin review — visible only to cnantasenamat / chaninn
# ---------------------------------------------------------------------------
if current_user not in ADMIN_USERS:
    st.stop()

st.divider()
with st.container(border=True):
    st.subheader(":material/admin_panel_settings: Admin Review")

    pending_df = raw[raw["STATUS"] == "PENDING"].copy()
    tab_pending, tab_promote = st.tabs([
        f"Pending ({len(pending_df)})",
        "Promotion History",
    ])

    # ── Tab 1: Pending ────────────────────────────────────────────────────
    with tab_pending:
        if pending_df.empty:
            st.info("No pending submissions.")
        else:
            review_cols = [
                "CANDIDATE_ID", "SUBMITTED_AT", "SUBMITTED_BY",
                "DOC_URL", "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
                "SCORE_TOTAL", "MH_PASS_RATE",
            ]
            review = pending_df[review_cols].copy()
            review.insert(0, "Approve", False)
            review.insert(1, "Reject",  False)

            edited = st.data_editor(
                review,
                column_config={
                    "Approve":      st.column_config.CheckboxColumn("Approve", default=False, width="small"),
                    "Reject":       st.column_config.CheckboxColumn("Reject",  default=False, width="small"),
                    "CANDIDATE_ID": None,
                    "SUBMITTED_AT": st.column_config.DatetimeColumn("Submitted", format="YYYY-MM-DD HH:mm"),
                    "SUBMITTED_BY": st.column_config.TextColumn("By"),
                    "DOC_URL":      st.column_config.LinkColumn("Doc URL"),
                    "QUESTION_TEXT":st.column_config.TextColumn("Question", width="large"),
                    "CATEGORY":     st.column_config.TextColumn("Category"),
                    "QUESTION_TYPE":st.column_config.TextColumn("Type"),
                    "SCORE_TOTAL":  st.column_config.ProgressColumn("Score /50", format="%.1f", min_value=0, max_value=50),
                    "MH_PASS_RATE": st.column_config.ProgressColumn("MH Pass", format="%.0f%%", min_value=0, max_value=1),
                },
                disabled=[
                    "SUBMITTED_AT", "SUBMITTED_BY", "DOC_URL",
                    "QUESTION_TEXT", "CATEGORY", "QUESTION_TYPE",
                    "SCORE_TOTAL", "MH_PASS_RATE",
                ],
                hide_index=True,
                use_container_width=True,
                key="pending_review_table",
            )

            to_approve = edited[edited["Approve"]]
            to_reject  = edited[edited["Reject"]]

            col_a, col_r, _ = st.columns([1, 1, 4])

            # ── Approve → promote to AEO_QUESTIONS ──────────────────────
            if col_a.button(
                f"Approve & Promote ({len(to_approve)})",
                type="primary",
                disabled=to_approve.empty,
                key="btn_approve",
            ):
                # Derive next Q ID from current MAX
                max_q_df = run_query(
                    f"SELECT MAX(CAST(SUBSTR(QUESTION_ID, 2) AS INT)) AS max_num "
                    f"FROM {DB}.{SCH}.AEO_QUESTIONS"
                )
                next_num = int(max_q_df.iloc[0]["MAX_NUM"] or 0) + 1

                promoted = []
                for _, row in to_approve.iterrows():
                    cid     = int(row["CANDIDATE_ID"])
                    q_id    = f"Q{next_num:03d}"
                    next_num += 1

                    # Fetch full candidate row for must-haves + canonical answer
                    full = raw[raw["CANDIDATE_ID"] == cid].iloc[0]

                    run_write(
                        f"""INSERT INTO {DB}.{SCH}.AEO_QUESTIONS
                            (QUESTION_ID, QUESTION_TEXT, CATEGORY, QUESTION_TYPE,
                             CANONICAL_ANSWER,
                             MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
                             DOC_URL)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        params=[
                            q_id,
                            full["QUESTION_TEXT"], full["CATEGORY"], full["QUESTION_TYPE"],
                            full.get("CANONICAL_ANSWER"),
                            full.get("MUST_HAVE_1"), full.get("MUST_HAVE_2"),
                            full.get("MUST_HAVE_3"), full.get("MUST_HAVE_4"),
                            full.get("MUST_HAVE_5"),
                            full.get("DOC_URL"),
                        ],
                    )
                    run_write(
                        """UPDATE AEO_DOC_CANDIDATES
                           SET STATUS      = 'APPROVED',
                               REVIEWED_BY = CURRENT_USER(),
                               REVIEWED_AT = CURRENT_TIMESTAMP()
                           WHERE CANDIDATE_ID = ?""",
                        params=[cid],
                    )
                    promoted.append(q_id)

                run_query.clear()
                st.success(
                    f"Promoted {len(promoted)} candidate(s) to benchmark: "
                    + ", ".join(f"`{q}`" for q in promoted)
                )
                st.rerun()

            # ── Reject ───────────────────────────────────────────────────
            if col_r.button(
                f"Reject ({len(to_reject)})",
                disabled=to_reject.empty,
                key="btn_reject",
            ):
                for _, row in to_reject.iterrows():
                    run_write(
                        """UPDATE AEO_DOC_CANDIDATES
                           SET STATUS      = 'REJECTED',
                               REVIEWED_BY = CURRENT_USER(),
                               REVIEWED_AT = CURRENT_TIMESTAMP()
                           WHERE CANDIDATE_ID = ?""",
                        params=[int(row["CANDIDATE_ID"])],
                    )
                run_query.clear()
                st.success(f"Rejected {len(to_reject)} candidate(s).")
                st.rerun()

    # ── Tab 2: Promotion history ──────────────────────────────────────────
    with tab_promote:
        hist_df = raw[raw["STATUS"] == "APPROVED"][
            ["CANDIDATE_ID", "QUESTION_TEXT", "CATEGORY", "SCORE_TOTAL",
             "MH_PASS_RATE", "REVIEWED_BY", "REVIEWED_AT"]
        ].copy()

        if hist_df.empty:
            st.info("No approved candidates yet.")
        else:
            st.caption(f"{len(hist_df)} candidate(s) promoted to `{DB}.{SCH}.AEO_QUESTIONS`.")
            st.dataframe(
                hist_df.rename(columns={
                    "CANDIDATE_ID":  "ID",
                    "QUESTION_TEXT": "Question",
                    "CATEGORY":      "Category",
                    "SCORE_TOTAL":   "Score /50",
                    "MH_PASS_RATE":  "MH Pass",
                    "REVIEWED_BY":   "Reviewed By",
                    "REVIEWED_AT":   "Reviewed At",
                }),
                column_config={
                    "Score /50": st.column_config.ProgressColumn(
                        "Score /50", format="%.1f", min_value=0, max_value=50
                    ),
                    "MH Pass": st.column_config.ProgressColumn(
                        "MH Pass", format="%.0f%%", min_value=0, max_value=1
                    ),
                    "Reviewed At": st.column_config.DatetimeColumn(
                        "Reviewed At", format="YYYY-MM-DD HH:mm"
                    ),
                    "Question": st.column_config.TextColumn("Question", width="large"),
                },
                use_container_width=True,
                hide_index=True,
            )
