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
from utils.scoring import (  # noqa: E402
    generate_response,
    score_response,
    get_baseline_scores,
    load_question_bank,
    JUDGE_PANEL,
)

AVAILABLE_MODELS = ["claude-opus-4-6", "claude-opus-4-7", "openai-gpt-5.4", "llama4-maverick", "gemini-3.1-pro", "cortex-code"]
CORTEX_NATIVE = "cortex-code"
# Detected once at module load — drives local vs SiS code path throughout the page.
IS_SIS = is_sis()

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
            st.caption("- Generating evaluation criteria with Cortex…")
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
                    st.caption(f"- Evaluation criteria generated ({len(custom_must_haves)} must-haves).")
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
                if model == CORTEX_NATIVE:
                    if system_prompt:
                        _native_prompt = f"[SYSTEM PROMPT]\n{system_prompt}\n\n[QUESTION]\n{qt}"
                    else:
                        _native_prompt = qt
                    if not IS_SIS:
                        # Local: run cortex CLI directly
                        try:
                            _native_result = subprocess.run(
                                [shutil.which("cortex") or "cortex", "--print", _native_prompt, "--connection", "my-snowflake"],
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
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{qid or 'custom'}**: Running native Cortex Code via :blue[SPCS]")
                        from utils.spcs import run_via_spcs
                        response_text = run_via_spcs(
                            session, _native_prompt,
                            run_schema=f"{DB}.{SCH}",
                            warehouse=WH,
                            role=SPCS_ROLE,
                        )
                        if response_text.startswith("[Error:"):
                            st.error(f"SPCS job failed for {qid or 'custom'}: {response_text}")
                            continue
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
                         RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?)
                    """,
                    params=[
                        str(uuid.uuid4()), user_name, system_prompt or None,
                        qid, custom_question, qcat, model,
                        response_text,
                        avg["correctness"], avg["completeness"], avg["recency"],
                        avg["citation"], avg["recommendation"],
                        avg["total"], avg["must_have_pass"],
                        json.dumps(panel_result["judges"], default=str),
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
                baseline = get_baseline_scores(selected_qid) if (not multi_mode and selected_qid) else None
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
                        name="Baseline (run 1)",
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
                    if item["canonical"]:
                        with st.expander("Canonical answer (ground truth)"):
                            st.markdown(item["canonical"])
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
