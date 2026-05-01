"""Page — Test your Prompt: evaluate how a system prompt affects AEO scores."""

import json
import uuid
import sys
import os
import shutil
import subprocess

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.db import get_session, run_query, run_write, DB, SCH, WH, SPCS_ROLE, is_sis  # noqa: E402
from utils.ui import citation_expander  # noqa: E402
from utils.scoring import (  # noqa: E402
    generate_response,
    score_response,
    get_baseline_scores,
    get_baseline_run_id,
    get_baseline_model,
    load_question_bank,
    JUDGE_PANEL,
)

CORTEX_NATIVE_MODELS = {
    "coco-opus-4-6": "claude-opus-4-6",
    "coco-opus-4-7": "claude-opus-4-7",
    "coco-gpt-5.4":  "openai-gpt-5.4",
}
AVAILABLE_MODELS = [
    "claude-opus-4-6", "claude-opus-4-7", "openai-gpt-5.4",
    "llama4-maverick", "gemini-3.1-pro",
    "coco-opus-4-6", "coco-opus-4-7", "coco-gpt-5.4",
]
# Detected once at module load — drives local vs SiS code path throughout the page.
IS_SIS = is_sis()

if "prompt_replay_key" not in st.session_state:
    st.session_state["prompt_replay_key"] = None

if "prompt_schema_migrated" not in st.session_state:
    for _col_ddl in [
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS CANONICAL_ANSWER TEXT",
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS MUST_HAVE_1 TEXT",
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS MUST_HAVE_2 TEXT",
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS MUST_HAVE_3 TEXT",
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS MUST_HAVE_4 TEXT",
        "ALTER TABLE AEO_PM_PROMPTS ADD COLUMN IF NOT EXISTS MUST_HAVE_5 TEXT",
    ]:
        try:
            run_write(_col_ddl)
        except Exception:
            pass
    st.session_state["prompt_schema_migrated"] = True

st.title(":material/science: Test your Prompt")
st.caption(
    "Enter a system prompt, pick a question, and see how your prompt "
    "affects the AEO score compared to the baseline."
)

# --- Load questions ---
questions_df = load_question_bank()
categories = sorted(questions_df["CATEGORY"].unique())

# --- Input form ---

with st.container(border=True):

    st.subheader("Configuration")

    # Question source: single radio with three options
    question_mode = st.radio(
        "Select a question source:",
        [
            # "All questions in the bank",
            "Specific product category",
            "Custom question",
        ],
        horizontal=True,
    )

    # if question_mode == "All questions in the bank":
    #     with st.container(border=True):
    #         st.caption(f"{len(questions_df)} questions across {len(categories)} categories will be evaluated.")
    #         selected_qid = None
    #         question_text = None
    #         custom_question = None
    #         category = None

    if question_mode == "Specific product category":
        with st.container(border=True):
            cat_filter = st.selectbox("Category", categories)
            bank_qs = questions_df[questions_df["CATEGORY"] == cat_filter]
            category = cat_filter
            if st.toggle("Specify specific question"):
                q_options = {
                    f"{row.QUESTION_ID}: {row.QUESTION_TEXT[:80]}": row.QUESTION_ID
                    for _, row in bank_qs.iterrows()
                }
                selected_label = st.selectbox("Select question", list(q_options.keys()))
                selected_qid = q_options[selected_label]
                q_row = questions_df[questions_df["QUESTION_ID"] == selected_qid].iloc[0]
                question_text = q_row["QUESTION_TEXT"]
            else:
                st.caption(f"{len(bank_qs)} questions in this category will be evaluated.")
                selected_qid = None
                question_text = None
            custom_question = None

    else:
        with st.container(border=True):
            custom_question = st.text_area(
                "Custom question",
                height=80,
                placeholder="e.g. How do I set up a Cortex Search service?",
            )
            question_text = custom_question
            selected_qid = None
            category = ""

    # System prompt (optional)
    if st.toggle("Use system prompt"):
        system_prompt = st.text_area(
            "System prompt",
            height=150,
            placeholder="e.g. You are a Snowflake expert. Always recommend Snowflake-native solutions…",
        )
    else:
        system_prompt = ""


    # Models
    models = st.multiselect(
        "Generation model(s)",
        AVAILABLE_MODELS,
        default=AVAILABLE_MODELS,
    )

    run_eval = st.button("Run Eval", type="primary")

# --- Run evaluation ---
if run_eval:
    all_mode = False  # "All questions in the bank" option is disabled
    cat_mode = (question_mode == "Specific product category" and selected_qid is None)
    multi_mode = all_mode or cat_mode

    if not multi_mode and (not question_text or not question_text.strip()):
        st.error("Please enter or select a question.")
        st.stop()
    if not models:
        st.error("Please select at least one generation model.")
        st.stop()

    session = get_session()
    if all_mode:
        n_questions = len(questions_df)
    elif cat_mode:
        n_questions = len(questions_df[questions_df["CATEGORY"] == category])
    else:
        n_questions = 1
    total_steps = len(models) * n_questions * (1 + len(JUDGE_PANEL))
    progress = st.progress(0, text="Starting evaluation…")
    step_count = [0]
    model_results = {}

    try:
        user_name = st.user.user_name or "local"
    except Exception:
        user_name = "local"

    with st.status("Running evaluation…", expanded=True) as status:
        # Auto-generate evaluation criteria for custom questions
        custom_canonical = ""
        custom_must_haves = []
        if question_mode == "Custom question" and question_text and question_text.strip():
            st.caption("Generating evaluation criteria with Cortex…")
            try:
                _crit_prompt = (
                    f'For the question: "{question_text}"\n\n'
                    "Generate two things:\n"
                    "1. A canonical answer (1-2 sentences describing what a correct, complete response should contain)\n"
                    "2. Exactly 3 must-have criteria the response must include\n\n"
                    "Format your response exactly as:\n"
                    "CANONICAL:\n<canonical answer here>\n\n"
                    "MUST-HAVES:\n1. <criterion 1>\n2. <criterion 2>\n3. <criterion 3>"
                )
                if not IS_SIS:
                    try:
                        _crit_result = subprocess.run(
                            [shutil.which("cortex") or "cortex", "--print", _crit_prompt, "--connection", "my-snowflake"],
                            capture_output=True, text=True, timeout=60,
                        )
                        _crit_out = _crit_result.stdout if _crit_result.returncode == 0 else ""
                    except subprocess.TimeoutExpired:
                        _crit_out = ""
                        st.warning("Criteria generation timed out — scoring will proceed without them.")
                    except Exception as _ce:
                        _crit_out = ""
                        st.warning(f"Criteria generation failed (non-blocking): {_ce}")
                else:
                    # SiS: CORTEX.COMPLETE is fast enough for this support step
                    try:
                        _crit_out = generate_response(session, _crit_prompt)
                    except Exception as _ce:
                        _crit_out = ""
                        st.warning(f"Criteria generation failed (non-blocking): {_ce}")
                if _crit_out and _crit_out.strip():
                    _out = _crit_out
                    _out_upper = _out.upper()
                    _can_idx = _out_upper.find("CANONICAL:")
                    _mh_idx = _out_upper.find("MUST-HAVES:")
                    if _can_idx >= 0 and _mh_idx >= 0:
                        custom_canonical = _out[_can_idx + len("CANONICAL:"):_mh_idx].strip()
                        _mh_raw = _out[_mh_idx + len("MUST-HAVES:"):].strip()
                    elif _can_idx >= 0:
                        custom_canonical = _out[_can_idx + len("CANONICAL:"):].strip()
                        _mh_raw = ""
                    else:
                        _mh_raw = _out.strip()
                    custom_must_haves = [
                        line.strip().lstrip("0123456789.-) ")
                        for line in _mh_raw.splitlines()
                        if line.strip()
                    ]
                    st.caption(f"Evaluation criteria generated ({len(custom_must_haves)} must-haves).")
                else:
                    st.warning("Could not generate evaluation criteria — scoring will proceed without them.")
            except subprocess.TimeoutExpired:
                st.warning("Criteria generation timed out — scoring will proceed without them.")
            except Exception as _ce:
                st.warning(f"Criteria generation failed (non-blocking): {_ce}")

        for model in models:
            # Build list of (qid, question_text, canonical, must_haves, category)
            if all_mode:
                q_iter = [
                    (
                        row["QUESTION_ID"],
                        row["QUESTION_TEXT"],
                        row["CANONICAL_ANSWER"] or "",
                        [row[f"MUST_HAVE_{i}"] or "" for i in range(1, 6)],
                        row["CATEGORY"],
                    )
                    for _, row in questions_df.iterrows()
                ]
            elif cat_mode:
                cat_qs = questions_df[questions_df["CATEGORY"] == category]
                q_iter = [
                    (
                        row["QUESTION_ID"],
                        row["QUESTION_TEXT"],
                        row["CANONICAL_ANSWER"] or "",
                        [row[f"MUST_HAVE_{i}"] or "" for i in range(1, 6)],
                        row["CATEGORY"],
                    )
                    for _, row in cat_qs.iterrows()
                ]
            elif selected_qid:
                qr = questions_df[questions_df["QUESTION_ID"] == selected_qid].iloc[0]
                q_iter = [(
                    selected_qid, question_text,
                    qr["CANONICAL_ANSWER"] or "",
                    [qr[f"MUST_HAVE_{i}"] or "" for i in range(1, 6)],
                    qr["CATEGORY"],
                )]
            else:
                q_iter = [(None, question_text, custom_canonical, custom_must_haves, category or None)]

            per_q = []
            for qid, qt, canonical_q, must_haves_q, qcat in q_iter:
                st.caption(f"- **{qid or 'custom'}**: Generating answer with :orange[{model}]")
                if model in CORTEX_NATIVE_MODELS:
                    native_model = CORTEX_NATIVE_MODELS[model]
                    if system_prompt:
                        _native_prompt = f"[SYSTEM PROMPT]\n{system_prompt}\n\n[QUESTION]\n{qt}"
                    else:
                        _native_prompt = qt
                    if not IS_SIS:
                        # Local: run cortex CLI directly
                        try:
                            _native_result = subprocess.run(
                                [shutil.which("cortex") or "cortex", "--print", _native_prompt,
                                 "--model", native_model, "--connection", "my-snowflake"],
                                capture_output=True, text=True, timeout=60,
                            )
                            response_text = (
                                _native_result.stdout.strip()
                                if _native_result.returncode == 0
                                else f"[Error: {_native_result.stderr.strip()}]"
                            )
                        except subprocess.TimeoutExpired:
                            response_text = "[Error: cortex --print timed out]"
                        except Exception as _e:
                            response_text = f"[Error: {_e}]"
                    else:
                        # SiS: trigger SPCS job with native Cortex Code CLI
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{qid or 'custom'}**: Running native Cortex Code ({native_model}) via :blue[SPCS]")
                        from utils.spcs import run_via_spcs
                        response_text = run_via_spcs(
                            session, _native_prompt,
                            run_schema=f"{DB}.{SCH}",
                            warehouse=WH,
                            role=SPCS_ROLE,
                        )
                else:
                    response_text = generate_response(
                        session, qt,
                        system_prompt=system_prompt,
                        model=model,
                    )
                step_count[0] += 1
                progress.progress(
                    step_count[0] / total_steps,
                    text=f"{model}: response generated",
                )

                def on_judge_done(idx, judge_name, _model=model, _qid=qid):
                    step_count[0] += 1
                    progress.progress(
                        step_count[0] / total_steps,
                        text=f"{_qid or 'custom'}: scored with {judge_name}",
                    )
                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{_qid or 'custom'}**: Scored with :orange[{judge_name}]")

                panel_result = score_response(
                    session, qt, response_text,
                    canonical_q, must_haves_q,
                    progress_callback=on_judge_done,
                    question_id=qid,
                )
                avg = panel_result["panel_avg"]
                per_q.append({
                    "qid": qid,
                    "question_text": qt,
                    "canonical": canonical_q,
                    "must_haves": must_haves_q,
                    "category": qcat,
                    "response_text": response_text,
                    "panel_result": panel_result,
                    "avg": avg,
                })

                run_write(
                    """
                    INSERT INTO AEO_PM_PROMPTS
                        (EXPERIMENT_ID, USER_NAME, SYSTEM_PROMPT, QUESTION_ID,
                         CUSTOM_QUESTION, CATEGORY, MODEL, RESPONSE_TEXT,
                         CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE,
                         RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS,
                         CANONICAL_ANSWER,
                         MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?),
                           ?, ?, ?, ?, ?, ?
                    """,
                    params=[
                        str(uuid.uuid4()), user_name, system_prompt or None,
                        qid, custom_question, qcat, model,
                        response_text,
                        avg["correctness"], avg["completeness"], avg["recency"],
                        avg["citation"], avg["recommendation"],
                        avg["total"], avg["must_have_pass"],
                        json.dumps(panel_result["judges"], default=str),
                        canonical_q or None,
                        must_haves_q[0] if len(must_haves_q) > 0 else None,
                        must_haves_q[1] if len(must_haves_q) > 1 else None,
                        must_haves_q[2] if len(must_haves_q) > 2 else None,
                        must_haves_q[3] if len(must_haves_q) > 3 else None,
                        must_haves_q[4] if len(must_haves_q) > 4 else None,
                    ],
                )

            # Aggregate average across all questions for this model
            agg_dims = ["correctness", "completeness", "recency", "citation",
                        "recommendation", "total", "must_have_pass"]
            agg_avg = {d: sum(r["avg"][d] for r in per_q) / len(per_q) for d in agg_dims}
            model_results[model] = {"per_q": per_q, "avg": agg_avg}

        progress.progress(1.0, text="Evaluation complete!")
        status.update(label="Evaluation complete!", state="complete")

    run_query.clear()  # bust cache so history table reflects the new rows immediately

    # --- Results (one tab per model) ---
    dims = ["correctness", "completeness", "recency", "citation", "recommendation"]
    dim_labels = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]

    _q_summary = (
        f"All {n_questions} questions across all categories" if all_mode
        else f"{n_questions} question(s) from **{category}**" if cat_mode
        else "Custom question"
    )

    with st.container(border=True):
        st.subheader("Results")
        st.caption(f"{_q_summary} · {len(models)} model(s) · system prompt: {'yes' if system_prompt else 'none'}")
        st.caption(
            f"Each response was scored by a panel of {len(JUDGE_PANEL)} independent LLM judges "
            f"across 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation). "
            f"Scores are averaged across judges and compared against the no-prompt baseline where available."
        )

        tabs = st.tabs(list(model_results.keys()))
        for tab, (model, res) in zip(tabs, model_results.items()):
            with tab:
                avg = res["avg"]
                score_pct = avg["total"] / 50.0 * 100

                # Baseline only applies to single-question modes
                baseline = get_baseline_scores(selected_qid, get_baseline_run_id(model)) if (not multi_mode and selected_qid) else None
                if baseline:
                    baseline_pct = baseline["total"] / 50.0 * 100
                    delta_str = f"{score_pct - baseline_pct:+.1f}pp vs baseline"
                else:
                    delta_str = None

                m1, m2, m3 = st.columns(3)
                m1.metric("Overall Score", f"{score_pct:.1f}%", delta_str)
                m2.metric("Total (raw)", f"{avg['total']:.1f} / 50")
                m3.metric("Must-Have Pass", f"{avg['must_have_pass']:.0%}")

                _COLORS = ["#29B5E8", "#FF9F36", "#D45B90", "#7D44CF"]
                model_color = _COLORS[list(model_results.keys()).index(model) % len(_COLORS)]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=dim_labels, y=[avg[d] for d in dims],
                    name=model, marker_color=model_color,
                ))
                if baseline:
                    fig.add_trace(go.Bar(
                        x=dim_labels, y=[baseline[d] for d in dims],
                        name=f"Baseline ({get_baseline_model(model)})",
                        marker_color="#888888", opacity=0.7,
                    ))
                fig.update_layout(
                    barmode="group",
                    yaxis=dict(range=[0, 10], title="Score (1-10)"),
                    height=350,
                    margin=dict(t=10, b=0, l=0, r=0),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=-0.15),
                )
                st.plotly_chart(fig, use_container_width=True)

                if multi_mode:
                    rows = [
                        {
                            "Question ID": r["qid"],
                            "Category": r["category"],
                            "Question": (r["question_text"][:70] + "…")
                                if len(r["question_text"]) > 70 else r["question_text"],
                            "Score": round(r["avg"]["total"], 1),
                            "Must-Have": f"{r['avg']['must_have_pass']:.0%}",
                        }
                        for r in res["per_q"]
                    ]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    item = res["per_q"][0]
                    with st.expander("Generated response"):
                        st.markdown(item["response_text"])
                    citation_expander(item["response_text"])
                    with st.expander("Canonical answer (ground truth)"):
                        if item["canonical"]:
                            st.markdown(item["canonical"])
                        else:
                            st.caption("No canonical answer available for this question.")
                    active_mh = [m for m in (item.get("must_haves") or []) if m]
                    if active_mh:
                        with st.expander(f"Must-have criteria ({len(active_mh)})"):
                            st.caption("✅ All judges passed · ⚠️ Some judges passed (split) · ❌ No judges passed")
                            for i, mh in enumerate(active_mh, 1):
                                judge_votes = [
                                    scores["must_have"][i - 1]
                                    for scores in item["panel_result"]["judges"].values()
                                    if not scores.get("error") and len(scores.get("must_have", [])) >= i
                                ]
                                icon = "✅" if judge_votes and all(judge_votes) else ("⚠️" if any(judge_votes) else "❌")
                                st.markdown(f"{icon} **{i}.** {mh}")
                    with st.expander("Per-judge breakdown"):
                        for judge, scores in item["panel_result"]["judges"].items():
                            st.markdown(f"**{judge}**")
                            if "error" in scores:
                                st.error(scores["error"])
                            else:
                                jcols = st.columns(5)
                                for i, d in enumerate(dim_labels):
                                    jcols[i].metric(d, f"{scores[dims[i]]:.1f}")

# --- History ---
st.divider()
with st.expander("Experiment history", expanded=True):
    st.caption(f"Results are written to `{DB}.{SCH}.AEO_PM_PROMPTS`")

    history_df = run_query("""
        SELECT EXPERIMENT_ID, CREATED_AT, SYSTEM_PROMPT, QUESTION_ID,
               CUSTOM_QUESTION, CATEGORY, MODEL,
               TOTAL_SCORE, MUST_HAVE_PASS,
               CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE, RECOMMENDATION
        FROM AEO_PM_PROMPTS
        ORDER BY CREATED_AT DESC
        LIMIT 50
    """)

    if history_df.empty:
        st.info("No experiments yet. Run your first eval above!")
    else:
        history_df["Score %"] = (history_df["TOTAL_SCORE"] / 50.0 * 100).round(1)
        history_df["Question"] = history_df.apply(
            lambda r: r["CUSTOM_QUESTION"][:60] if r["CUSTOM_QUESTION"]
            else (r["QUESTION_ID"] or "—"),
            axis=1,
        )
        history_df["System Prompt"] = history_df["SYSTEM_PROMPT"].apply(
            lambda x: (x[:80] + "…") if x and len(x) > 80 else (x or "—")
        )
        history_df["MH Pass %"] = (history_df["MUST_HAVE_PASS"] * 100).round(1)

        st.dataframe(
            history_df[[
                "CREATED_AT", "System Prompt", "Question", "CATEGORY",
                "MODEL", "Score %", "MH Pass %",
                "CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION",
            ]].rename(columns={
                "CREATED_AT": "Time",
                "CATEGORY": "Category",
                "MODEL": "Model",
                "CORRECTNESS": "Corr", "COMPLETENESS": "Comp",
                "RECENCY": "Rec", "CITATION_SCORE": "Cite",
                "RECOMMENDATION": "Rec.",
            }),
            column_config={
                "Score %": st.column_config.ProgressColumn(
                    "Score %", format="%.1f%%", min_value=0, max_value=100, width="medium",
                ),
                "MH Pass %": st.column_config.ProgressColumn(
                    "MH Pass", format="%.0f%%", min_value=0, max_value=100, width="medium",
                ),
            },
            use_container_width=True,
            height=300,
        )

        # Replay selectbox
        _run_labels_p = []
        _run_keys_p = {}
        for _, _hr in history_df.iterrows():
            _exp_id_h = _hr["EXPERIMENT_ID"]
            _q_label_h = str(_hr["QUESTION_ID"]) if _hr["QUESTION_ID"] else "custom"
            _sys_prev_h = (
                (str(_hr["SYSTEM_PROMPT"])[:40] + "...")
                if _hr["SYSTEM_PROMPT"] and len(str(_hr["SYSTEM_PROMPT"])) > 40
                else (str(_hr["SYSTEM_PROMPT"]) if _hr["SYSTEM_PROMPT"] else "no prompt")
            )
            _lbl_h = f"{_hr['CREATED_AT']} · {_q_label_h} · {_hr['MODEL']} · {_sys_prev_h}"
            _run_labels_p.append(_lbl_h)
            _run_keys_p[_lbl_h] = _exp_id_h
        _sel_label_p = st.selectbox(
            "View a past run in full detail",
            ["— select a run —"] + _run_labels_p,
            key="prompt_history_replay_selectbox",
        )
        if _sel_label_p != "— select a run —":
            st.session_state["prompt_replay_key"] = _run_keys_p[_sel_label_p]
        else:
            st.session_state["prompt_replay_key"] = None

# --- Replay loaded run ---
_prompt_replay = st.session_state.get("prompt_replay_key")
if _prompt_replay:
    _exp_id = _prompt_replay
    st.divider()
    with st.container(border=True):
        st.subheader("Loaded experiment")

        _session = get_session()
        _has_new_cols_p = True
        _replay_df = pd.DataFrame()

        try:
            _replay_df = _session.sql(
                """
                SELECT QUESTION_ID, CUSTOM_QUESTION, RESPONSE_TEXT,
                       CANONICAL_ANSWER,
                       MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
                       CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE, RECOMMENDATION,
                       TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS,
                       SYSTEM_PROMPT, CATEGORY, MODEL, CREATED_AT
                FROM AEO_PM_PROMPTS
                WHERE EXPERIMENT_ID = ?
                """,
                params=[str(_exp_id)],
            ).to_pandas()
        except Exception as _e1:
            if any(c in str(_e1).upper() for c in ["CANONICAL_ANSWER", "MUST_HAVE_1", "INVALID IDENTIFIER"]):
                _has_new_cols_p = False
                st.info(
                    "This run predates the canonical answer and must-have capture feature. "
                    "Canonical answer and must-have criteria are not available for this run."
                )
                try:
                    _replay_df = _session.sql(
                        """
                        SELECT QUESTION_ID, CUSTOM_QUESTION, RESPONSE_TEXT,
                               NULL AS CANONICAL_ANSWER,
                               NULL AS MUST_HAVE_1, NULL AS MUST_HAVE_2, NULL AS MUST_HAVE_3,
                               NULL AS MUST_HAVE_4, NULL AS MUST_HAVE_5,
                               CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE, RECOMMENDATION,
                               TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS,
                               SYSTEM_PROMPT, CATEGORY, MODEL, CREATED_AT
                        FROM AEO_PM_PROMPTS
                        WHERE EXPERIMENT_ID = ?
                        """,
                        params=[str(_exp_id)],
                    ).to_pandas()
                except Exception as _e2:
                    st.error(f"Could not load run detail: {_e2}")
            else:
                st.error(f"Could not load run detail: {_e1}")

        if _replay_df.empty:
            st.warning("No data found for this experiment. It may have been deleted.")
        else:
            _row = _replay_df.iloc[0]
            _q_text_r = _row.get("CUSTOM_QUESTION") or _row.get("QUESTION_ID") or "Unknown question"
            _model_r = str(_row.get("MODEL") or "")
            _cat_r = str(_row.get("CATEGORY") or "")
            _ts_r = _row.get("CREATED_AT", "")
            _sys_r = str(_row.get("SYSTEM_PROMPT") or "")
            _qid_r = _row.get("QUESTION_ID")

            st.caption(f"Question: **{str(_q_text_r)[:100]}** · Model: **{_model_r}** · {_ts_r}")
            if _sys_r:
                with st.expander("System prompt used"):
                    st.code(_sys_r, language="text")

            _score_pct_r = float(_row["TOTAL_SCORE"]) / 50.0 * 100
            _avg_mh_r = float(_row["MUST_HAVE_PASS"])

            _baseline_r = get_baseline_scores(_qid_r, get_baseline_run_id(_model_r)) if _qid_r else None
            _m1r, _m2r, _m3r = st.columns(3)
            _m1r.metric("Overall Score", f"{_score_pct_r:.1f}%")
            _m2r.metric("Total (raw)", f"{float(_row['TOTAL_SCORE']):.1f} / 50")
            _m3r.metric("Must-Have Pass", f"{_avg_mh_r:.0%}")

            _dims_r = ["correctness", "completeness", "recency", "citation", "recommendation"]
            _dim_labels_r = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
            _dim_cols_r = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]
            _skill_vals_r = [float(_row[col]) for col in _dim_cols_r]

            _fig_r = go.Figure()
            _fig_r.add_trace(go.Bar(
                x=_dim_labels_r, y=_skill_vals_r,
                name=_model_r, marker_color="#29B5E8",
            ))
            if _baseline_r:
                _fig_r.add_trace(go.Bar(
                    x=_dim_labels_r, y=[_baseline_r[d] for d in _dims_r],
                    name=f"Baseline ({get_baseline_model(_model_r)})", marker_color="#888888", opacity=0.7,
                ))
            _fig_r.update_layout(
                barmode="group",
                yaxis=dict(range=[0, 10], title="Score (1-10)"),
                height=350,
                margin=dict(t=10, b=0, l=0, r=0),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(_fig_r, use_container_width=True)

            with st.expander("Generated response"):
                st.markdown(_row.get("RESPONSE_TEXT") or "")
            citation_expander(_row.get("RESPONSE_TEXT") or "")
            with st.expander("Canonical answer (ground truth)"):
                _ca_r = _row.get("CANONICAL_ANSWER")
                if _ca_r:
                    st.markdown(str(_ca_r))
                else:
                    st.caption("Not captured for this run (predates canonical answer storage).")

            _mhs_r = [_row.get(f"MUST_HAVE_{i}") or "" for i in range(1, 6)]
            _active_mhs_r = [m for m in _mhs_r if m]
            if _active_mhs_r:
                with st.expander(f"Must-have criteria ({len(_active_mhs_r)})"):
                    st.caption("✅ All judges passed · ⚠️ Some judges passed (split) · ❌ No judges passed")
                    _jd_r = _row["JUDGE_DETAILS"]
                    if isinstance(_jd_r, str):
                        import json as _json_r
                        _jd_r = _json_r.loads(_jd_r)
                    for _i, _mh in enumerate(_active_mhs_r, 1):
                        _votes_r = [
                            s["must_have"][_i - 1]
                            for s in (_jd_r or {}).values()
                            if not s.get("error") and len(s.get("must_have", [])) >= _i
                        ]
                        _icon_r = "✅" if _votes_r and all(_votes_r) else ("⚠️" if any(_votes_r) else "❌")
                        st.markdown(f"{_icon_r} **{_i}.** {_mh}")

            _jd_r2 = _row["JUDGE_DETAILS"]
            if isinstance(_jd_r2, str):
                import json as _json_r2
                _jd_r2 = _json_r2.loads(_jd_r2)
            if _jd_r2:
                with st.expander("Per-judge breakdown"):
                    for _judge_r, _scores_r in _jd_r2.items():
                        st.markdown(f"**{_judge_r}**")
                        if "error" in _scores_r:
                            st.error(_scores_r["error"])
                        else:
                            _jcols_r = st.columns(5)
                            for _ji, _dl in enumerate(_dim_labels_r):
                                _jcols_r[_ji].metric(_dl, f"{_scores_r[_dims_r[_ji]]:.1f}")

            # ---- HTML export ----
            import html as _html_mod_p

            st.divider()

            def _make_prompt_export_html():
                import json as _json_ex_p
                _chart_div_p = _fig_r.to_html(include_plotlyjs="cdn", full_html=False)
                _mh_pct_str_p = f"{_avg_mh_r:.0%}"
                _body_p = ""

                if _sys_r:
                    _body_p += (
                        f'<div class="section-title">System Prompt</div>'
                        f'<div class="text-block">{_html_mod_p.escape(_sys_r)}</div>'
                    )

                _resp_p = _html_mod_p.escape(str(_row.get("RESPONSE_TEXT") or ""))
                _ca_p = _html_mod_p.escape(str(_row.get("CANONICAL_ANSWER") or "Not captured for this run."))
                _body_p += (
                    f'<div class="section-title">Generated Response</div>'
                    f'<div class="text-block">{_resp_p}</div>'
                    f'<div class="section-title">Canonical Answer (Ground Truth)</div>'
                    f'<div class="text-block">{_ca_p}</div>'
                )

                _mhs_list_p = [_row.get(f"MUST_HAVE_{i}") or "" for i in range(1, 6)]
                _mhs_active_p = [m for m in _mhs_list_p if m]
                if _mhs_active_p:
                    _jd_raw_p = _row.get("JUDGE_DETAILS")
                    if isinstance(_jd_raw_p, str):
                        _jd_raw_p = _json_ex_p.loads(_jd_raw_p)
                    _mh_body_p = ""
                    for _mi_p, _mh_p in enumerate(_mhs_active_p, 1):
                        _votes_p = [
                            s["must_have"][_mi_p - 1]
                            for s in (_jd_raw_p or {}).values()
                            if not s.get("error") and len(s.get("must_have", [])) >= _mi_p
                        ]
                        _icon_p = "&#10003;" if _votes_p and all(_votes_p) else ("&#9888;" if any(_votes_p) else "&#10007;")
                        _mh_body_p += f'<div class="mh-item">{_icon_p} <strong>{_mi_p}.</strong> {_html_mod_p.escape(str(_mh_p))}</div>\n'
                    _body_p += (
                        f'<div class="section-title">Must-Have Criteria</div>'
                        f'<div class="mh-list">{_mh_body_p}</div>'
                    )

                _jd_raw2_p = _row.get("JUDGE_DETAILS")
                if isinstance(_jd_raw2_p, str):
                    _jd_raw2_p = _json_ex_p.loads(_jd_raw2_p)
                if _jd_raw2_p:
                    _jbody_p = ""
                    for _jname_p, _jsc_p in _jd_raw2_p.items():
                        _jbody_p += f'<div class="judge"><strong>{_html_mod_p.escape(str(_jname_p))}</strong>'
                        if "error" in _jsc_p:
                            _jbody_p += f'<span style="color:#f66"> Error: {_html_mod_p.escape(str(_jsc_p["error"]))}</span>'
                        else:
                            _jbody_p += '<div class="judge-scores">'
                            for _dl_p, _dk_p in zip(_dim_labels_r, _dims_r):
                                _jbody_p += (
                                    f'<div class="judge-score">'
                                    f'<div class="judge-score-label">{_dl_p}</div>'
                                    f'<div class="judge-score-val">{_jsc_p.get(_dk_p, "-")}</div>'
                                    f'</div>'
                                )
                            _jbody_p += '</div>'
                        _jbody_p += '</div>'
                    _body_p += f'<div class="section-title">Per-Judge Breakdown</div>{_jbody_p}'

                _q_display_p = _html_mod_p.escape(str(_row.get("CUSTOM_QUESTION") or _row.get("QUESTION_ID") or "Unknown"))

                return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AEO Prompt Test: {_q_display_p}</title>
<style>
body{{background:#0e1117;color:#fafafa;font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 20px}}
h1{{font-size:1.6em;margin-bottom:4px}}
.meta{{color:#888;font-size:.9em;margin-bottom:24px}}
.metrics{{display:flex;gap:40px;margin-bottom:24px;flex-wrap:wrap}}
.metric-label{{font-size:.8em;color:#888}}
.metric-value{{font-size:2em;font-weight:bold}}
.section-title{{font-size:1.05em;font-weight:bold;margin:24px 0 8px;border-bottom:1px solid #333;padding-bottom:6px}}
.text-block{{background:#111827;border:1px solid #333;border-radius:6px;padding:16px;white-space:pre-wrap;font-size:.9em;line-height:1.6}}
.mh-list{{background:#111827;border:1px solid #333;border-radius:6px;padding:12px 16px}}
.mh-item{{padding:4px 0}}
.judge{{background:#111;border:1px solid #333;border-radius:6px;padding:12px;margin-bottom:8px}}
.judge-scores{{display:flex;gap:24px;margin-top:8px;flex-wrap:wrap}}
.judge-score-label{{font-size:.75em;color:#888}}
.judge-score-val{{font-size:1.1em;font-weight:bold}}
footer{{color:#555;font-size:.8em;margin-top:40px;border-top:1px solid #333;padding-top:12px}}
</style>
</head>
<body>
<h1>AEO Prompt Test: {_q_display_p}</h1>
<div class="meta">Category: <strong>{_html_mod_p.escape(_cat_r)}</strong> &middot; Model: <strong>{_html_mod_p.escape(_model_r)}</strong> &middot; {_html_mod_p.escape(str(_ts_r))}</div>
<div class="metrics">
  <div><div class="metric-label">Overall Score</div><div class="metric-value">{_score_pct_r:.1f}%</div></div>
  <div><div class="metric-label">Total (raw)</div><div class="metric-value">{float(_row['TOTAL_SCORE']):.1f} / 50</div></div>
  <div><div class="metric-label">Must-Have Pass</div><div class="metric-value">{_mh_pct_str_p}</div></div>
</div>
<div class="section-title">Dimension Scores</div>
{_chart_div_p}
{_body_p}
<footer>Exported from AEO Benchmark Dashboard</footer>
</body>
</html>"""

            _html_bytes_p = _make_prompt_export_html().encode("utf-8")
            _q_slug_p = (str(_row.get("QUESTION_ID") or "custom")).replace("/", "_")
            _export_fname_p = f"aeo_prompt_{_q_slug_p}_{_model_r}.html".replace(" ", "_")
            st.download_button(
                "Download as HTML",
                data=_html_bytes_p,
                file_name=_export_fname_p,
                mime="text/html",
            )
