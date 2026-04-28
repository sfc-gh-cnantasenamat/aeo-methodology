"""Page — Test your Skill: evaluate how a CoCo skill affects AEO scores."""

import json
import uuid
import sys
import os
import shutil
import tempfile
import subprocess

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

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
# Detected once at module load — drives local vs SiS code path throughout the page.
IS_SIS = is_sis()

st.title(":material/extension: Test your Skill")
st.caption(
    "Upload a SKILL.md file, select a category, and see how the skill "
    "context affects AEO scores across that category's questions."
)

# --- Load questions ---
questions_df = load_question_bank()
categories = sorted(questions_df["CATEGORY"].unique())

# --- Input form ---
with st.container(border=True):
    st.subheader("Configuration")

    uploaded_file = st.file_uploader(
        "Upload SKILL.md",
        type=["md", "txt"],
        help="The skill file whose content will be injected as system context.",
    )

    if uploaded_file:
        skill_name = os.path.splitext(uploaded_file.name)[0]
        st.caption(f"Skill name: **{skill_name}**")
    else:
        skill_name = None

    category = st.selectbox("Category to evaluate", categories)

    cat_questions = questions_df[questions_df["CATEGORY"] == category]
    if st.toggle("Specify specific question"):
        q_options = {
            f"{row.QUESTION_ID}: {row.QUESTION_TEXT[:80]}": row.QUESTION_ID
            for _, row in cat_questions.iterrows()
        }
        selected_label = st.selectbox("Select question", list(q_options.keys()))
        selected_qid = q_options[selected_label]
        cat_questions = cat_questions[cat_questions["QUESTION_ID"] == selected_qid]
    else:
        st.caption(f"{len(cat_questions)} questions in **{category}** will be evaluated.")

    models = st.multiselect(
        "Generation model(s)",
        AVAILABLE_MODELS,
        default=AVAILABLE_MODELS,
    )

    run_eval = st.button("Run Eval", type="primary")

# --- Run evaluation ---
if run_eval:
    if not uploaded_file:
        st.error("Please upload a SKILL.md file.")
        st.stop()
    if not models:
        st.error("Please select at least one generation model.")
        st.stop()

    skill_content = uploaded_file.read().decode("utf-8")
    session = get_session()

    CORTEX_NATIVE = "cortex-code"
    all_models = list(models)

    # Upload skill to stage
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False,
        ) as tmp:
            tmp.write(skill_content)
            tmp_path = tmp.name

        stage_path = f"@{DB}.{SCH}.AEO_SKILL_STAGE/{skill_name}/"
        session.file.put(
            tmp_path, stage_path,
            auto_compress=False, overwrite=True,
        )
    except Exception as e:
        st.warning(f"Could not upload to stage (non-blocking): {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    n_questions = len(cat_questions)
    steps_per_q = 1 + len(JUDGE_PANEL)  # generate + 4 judges
    total_steps = len(all_models) * n_questions * steps_per_q
    step_count = [0]

    # model_results[model] = list of per-question result dicts
    model_results = {m: [] for m in all_models}

    try:
        user_name = st.user.user_name or "local"
    except Exception:
        user_name = "local"

    with st.status(
        f"Evaluating {n_questions} {'question' if n_questions == 1 else 'questions'} × {len(all_models)} {'model' if len(all_models) == 1 else 'models'}…",
        expanded=True,
    ) as status:
        progress = st.progress(0, text="Starting evaluation…")
        for model in all_models:
            for q_idx, (_, q_row) in enumerate(cat_questions.iterrows()):
                qid = q_row["QUESTION_ID"]
                q_text = q_row["QUESTION_TEXT"]
                canonical = q_row["CANONICAL_ANSWER"] or ""
                must_haves = [
                    q_row[f"MUST_HAVE_{i}"] or "" for i in range(1, 6)
                ]

                st.caption(f"- **{qid}**: Generating answer with :orange[{model}]")

                if model == CORTEX_NATIVE:
                    # Use cortex --print with skill content prepended as context
                    _native_prompt = (
                        f"[SKILL CONTEXT]\n{skill_content}\n\n"
                        f"[QUESTION]\n{q_text}"
                    )
                    _cortex_bin = shutil.which("cortex")
                    if not IS_SIS:
                        # Local: run cortex CLI directly
                        try:
                            _native_result = subprocess.run(
                                [_cortex_bin or "cortex", "--print", _native_prompt, "--connection", "my-snowflake"],
                                capture_output=True, text=True, timeout=60,
                            )
                            response_text = _native_result.stdout.strip() if _native_result.returncode == 0 else f"[Error: {_native_result.stderr.strip()}]"
                        except subprocess.TimeoutExpired:
                            response_text = "[Error: cortex --print timed out]"
                        except Exception as _e:
                            response_text = f"[Error: {_e}]"
                    else:
                        # SiS: trigger SPCS job with native Cortex Code CLI
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{qid}**: Running native Cortex Code via :blue[SPCS]")
                        from utils.spcs import run_via_spcs
                        response_text = run_via_spcs(
                            session, _native_prompt,
                            run_schema=f"{DB}.{SCH}",
                            warehouse=WH,
                            role=SPCS_ROLE,
                        )
                else:
                    response_text = generate_response(
                        session, q_text,
                        system_prompt=skill_content,
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
                        text=f"{_qid}: scored with {judge_name}",
                    )
                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{_qid}**: Scored with :orange[{judge_name}]")

                panel_result = score_response(
                    session, q_text, response_text,
                    canonical, must_haves,
                    progress_callback=on_judge_done,
                    question_id=qid,
                )

                avg = panel_result["panel_avg"]
                baseline = get_baseline_scores(qid)

                run_write(
                    """
                    INSERT INTO AEO_SKILL_TESTS
                        (TEST_ID, USER_NAME, SKILL_NAME,
                         QUESTION_ID, QUESTION_TEXT, CATEGORY, MODEL, RESPONSE_TEXT,
                         CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE,
                         RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_PASS,
                         JUDGE_DETAILS)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           PARSE_JSON(?)
                    """,
                    params=[
                        str(uuid.uuid4()), user_name, skill_name,
                        qid, q_text, category, model,
                        response_text,
                        avg["correctness"], avg["completeness"], avg["recency"],
                        avg["citation"], avg["recommendation"],
                        avg["total"], avg["must_have_pass"],
                        json.dumps(panel_result["judges"], default=str),
                    ],
                )

                model_results[model].append({
                    "QUESTION_ID": qid,
                    "question_text": q_text,
                    "canonical": canonical,
                    "must_haves": must_haves,
                    "response_text": response_text,
                    "avg": avg,
                    "baseline": baseline,
                    "panel_result": panel_result,
                    "judges": panel_result["judges"],
                })

        progress.progress(1.0, text="Evaluation complete!")
        status.update(label="Evaluation complete!", state="complete")

    run_query.clear()  # bust cache so history table reflects the new rows immediately

    dims = ["correctness", "completeness", "recency", "citation", "recommendation"]
    dim_labels = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
    _COLORS = ["#29B5E8", "#FF9F36", "#D45B90", "#7D44CF"]
    single_q = (n_questions == 1)

    with st.container(border=True):
        st.subheader("Results")
        st.caption(f"Skill: **{skill_name}** · Category: **{category}** · {n_questions} question(s) · {len(all_models)} model(s)")
        st.caption(
            f"Each response was scored by a panel of {len(JUDGE_PANEL)} independent LLM judges "
            f"across 5 dimensions (Correctness, Completeness, Recency, Citation, Recommendation). "
            f"Scores are averaged across judges and compared against the no-skill baseline where available."
        )

        tabs = st.tabs(list(model_results.keys()))
        for tab, (model, results) in zip(tabs, model_results.items()):
            with tab:
                if not results:
                    st.info("No results.")
                    continue

                model_color = _COLORS[list(model_results.keys()).index(model) % len(_COLORS)]
                avg = {d: sum(r["avg"][d] for r in results) / len(results) for d in dims + ["total", "must_have_pass"]}
                score_pct = avg["total"] / 50.0 * 100

                baseline_results = [r for r in results if r["baseline"]]
                if single_q and baseline_results:
                    bl = baseline_results[0]["baseline"]
                    baseline_pct = bl["total"] / 50.0 * 100
                    delta_str = f"{score_pct - baseline_pct:+.1f}pp vs baseline"
                else:
                    bl = None
                    delta_str = None

                m1, m2, m3 = st.columns(3)
                m1.metric("Overall Score", f"{score_pct:.1f}%", delta_str)
                m2.metric("Total (raw)", f"{avg['total']:.1f} / 50")
                m3.metric("Must-Have Pass", f"{avg['must_have_pass']:.0%}")

                # Bar chart: skill vs baseline dimensions
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=dim_labels, y=[avg[d] for d in dims],
                    name=model, marker_color=model_color,
                ))
                if bl:
                    fig.add_trace(go.Bar(
                        x=dim_labels, y=[bl[d] for d in dims],
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

                if single_q:
                    item = results[0]
                    with st.expander("Generated response"):
                        st.markdown(item["response_text"])
                    if item.get("canonical"):
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
                else:
                    # Multi-question: table + radar chart
                    all_rows = []
                    for r in results:
                        score_pct_q = r["avg"]["total"] / 50.0 * 100
                        bl_q = r["baseline"]
                        delta_q = (score_pct_q - bl_q["total"] / 50.0 * 100) if bl_q else None
                        all_rows.append({
                            "Question": r["QUESTION_ID"],
                            "Score %": round(score_pct_q, 1),
                            "Delta (pp)": round(delta_q, 1) if delta_q is not None else None,
                            "Correctness": round(r["avg"]["correctness"], 1),
                            "Completeness": round(r["avg"]["completeness"], 1),
                            "Recency": round(r["avg"]["recency"], 1),
                            "Citation": round(r["avg"]["citation"], 1),
                            "Recommendation": round(r["avg"]["recommendation"], 1),
                            "MH Pass": round(r["avg"]["must_have_pass"] * 100, 1),
                        })
                    st.dataframe(
                        pd.DataFrame(all_rows),
                        column_config={
                            "Score %": st.column_config.ProgressColumn(
                                "Score %", format="%.1f%%", min_value=0, max_value=100, width="medium",
                            ),
                            "MH Pass": st.column_config.ProgressColumn(
                                "MH Pass", format="%.0f%%", min_value=0, max_value=100, width="medium",
                            ),
                            "Delta (pp)": st.column_config.NumberColumn("Delta (pp)", format="%.1f"),
                        },
                        use_container_width=True,
                    )

                    # Radar: this model vs baseline
                    fig_radar = go.Figure()
                    skill_dim_avgs = [
                        sum(r["avg"][d] for r in results) / len(results) for d in dims
                    ]
                    fig_radar.add_trace(go.Scatterpolar(
                        r=skill_dim_avgs + [skill_dim_avgs[0]],
                        theta=dim_labels + [dim_labels[0]],
                        fill="toself", name=model, line_color=model_color,
                    ))
                    bl_results = [r for r in results if r["baseline"]]
                    if bl_results:
                        bl_dim_avgs = [
                            sum(r["baseline"][d] for r in bl_results) / len(bl_results)
                            for d in dims
                        ]
                        fig_radar.add_trace(go.Scatterpolar(
                            r=bl_dim_avgs + [bl_dim_avgs[0]],
                            theta=dim_labels + [dim_labels[0]],
                            fill="toself", name="Baseline",
                            line_color="#888888", opacity=0.5,
                        ))
                    fig_radar.update_layout(
                        polar=dict(
                            bgcolor="rgba(30,30,30,0.6)",
                            radialaxis=dict(range=[0, 10], gridcolor="#555555", linecolor="#555555", tickfont=dict(color="#cccccc")),
                            angularaxis=dict(gridcolor="#555555", linecolor="#555555", tickfont=dict(color="#cccccc")),
                        ),
                        height=420,
                        margin=dict(t=10, b=0, l=0, r=0),
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", y=-0.08, x=0.5, xanchor="center"),
                    )
                    st.plotly_chart(fig_radar, use_container_width=True)

# --- History ---
st.divider()
with st.expander("Skill test history", expanded=True):
    st.caption(f"Results are written to `{DB}.{SCH}.AEO_SKILL_TESTS`")

    try:
        history_df = run_query("""
            SELECT SKILL_NAME, CATEGORY, MODEL, CREATED_AT,
                   COUNT(*) AS QUESTIONS,
                   AVG(TOTAL_SCORE) AS AVG_TOTAL,
                   AVG(MUST_HAVE_PASS) AS AVG_MH_PASS,
                   AVG(CORRECTNESS) AS AVG_CORRECTNESS,
                   AVG(COMPLETENESS) AS AVG_COMPLETENESS,
                   AVG(RECENCY) AS AVG_RECENCY,
                   AVG(CITATION_SCORE) AS AVG_CITATION,
                   AVG(RECOMMENDATION) AS AVG_RECOMMENDATION
            FROM AEO_SKILL_TESTS
            GROUP BY SKILL_NAME, CATEGORY, MODEL, CREATED_AT
            ORDER BY CREATED_AT DESC
            LIMIT 50
        """)
        if history_df.empty:
            st.info("No skill tests yet. Run your first eval above!")
        else:
            history_df["Avg Score %"] = (
                history_df["AVG_TOTAL"] / 50.0 * 100
            ).round(1)
            history_df["MH Pass"] = (history_df["AVG_MH_PASS"] * 100).round(1)
            for col, label in [
                ("AVG_CORRECTNESS", "Correctness"),
                ("AVG_COMPLETENESS", "Completeness"),
                ("AVG_RECENCY", "Recency"),
                ("AVG_CITATION", "Citation"),
                ("AVG_RECOMMENDATION", "Recommendation"),
            ]:
                history_df[label] = history_df[col].round(1)

            st.dataframe(
                history_df[[
                    "CREATED_AT", "SKILL_NAME", "CATEGORY",
                    "MODEL", "QUESTIONS", "Avg Score %", "MH Pass",
                    "Correctness", "Completeness", "Recency", "Citation", "Recommendation",
                ]].rename(columns={
                    "CREATED_AT": "Time",
                    "SKILL_NAME": "Skill",
                    "CATEGORY": "Category",
                    "MODEL": "Model",
                    "QUESTIONS": "Qs",
                }),
                column_config={
                    "Avg Score %": st.column_config.ProgressColumn(
                        "Avg Score %", format="%.1f%%", min_value=0, max_value=100, width="medium",
                    ),
                    "MH Pass": st.column_config.ProgressColumn(
                        "MH Pass", format="%.0f%%", min_value=0, max_value=100, width="medium",
                    ),
                },
                use_container_width=True,
                height=300,
            )
    except Exception as _e:
        st.warning(f"Could not load history: {_e}")
