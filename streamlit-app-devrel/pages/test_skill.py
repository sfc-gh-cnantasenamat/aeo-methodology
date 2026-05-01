"""Page — Test your Skill: evaluate how a CoCo skill affects AEO scores."""

import io
import json
import uuid
import sys
import os
import shutil
import tempfile
import subprocess
import zipfile

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

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

# Session state for history replay
if "replay_run_key" not in st.session_state:
    st.session_state["replay_run_key"] = None

# Run schema migration once per browser session to ensure new columns exist
if "schema_migrated" not in st.session_state:
    for _col_ddl in [
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS CANONICAL_ANSWER TEXT",
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS MUST_HAVE_1 TEXT",
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS MUST_HAVE_2 TEXT",
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS MUST_HAVE_3 TEXT",
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS MUST_HAVE_4 TEXT",
        "ALTER TABLE AEO_SKILL_TESTS ADD COLUMN IF NOT EXISTS MUST_HAVE_5 TEXT",
    ]:
        try:
            run_write(_col_ddl)
        except Exception:
            pass
    st.session_state["schema_migrated"] = True

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
        "Upload SKILL.md or skill ZIP archive",
        type=["md", "txt", "zip"],
        help="Upload a single SKILL.md for one skill, or a ZIP archive of a skill directory. "
             "For ZIP uploads the root SKILL.md is used as the entry point. "
             "Non-coco models will only see the root SKILL.md content.",
    )

    if uploaded_file:
        skill_name = os.path.splitext(uploaded_file.name)[0]
        is_zip = uploaded_file.name.lower().endswith(".zip")
        if is_zip:
            st.caption(f"Skill suite (ZIP): **{skill_name}**")
            st.info(
                "ZIP detected. For non-coco models only the root SKILL.md will be "
                "used as system context. Sub-skills are fully resolved only for the "
                "coco model via the skill stage."
            )
        else:
            st.caption(f"Skill name: **{skill_name}**")
    else:
        skill_name = None
        is_zip = False

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

    file_bytes = uploaded_file.read()
    zip_extract_dir = None

    if is_zip:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            names = zf.namelist()
            # Find root SKILL.md: prefer bare "SKILL.md", then shallowest match
            root_md = next(
                (n for n in names if n == "SKILL.md"),
                next(
                    (
                        n for n in sorted(names, key=lambda x: x.count("/"))
                        if n.lower().endswith("skill.md")
                    ),
                    None,
                ),
            )
            if root_md is None:
                st.error("No SKILL.md found in the ZIP archive.")
                st.stop()
            skill_content = zf.read(root_md).decode("utf-8")
            zip_extract_dir = tempfile.mkdtemp()
            zf.extractall(zip_extract_dir)
    else:
        skill_content = file_bytes.decode("utf-8")

    session = get_session()

    all_models = list(models)

    # Upload skill to stage
    tmp_path = None
    try:
        if is_zip and zip_extract_dir:
            # Upload all extracted files preserving directory structure
            stage_base = f"@{DB}.{SCH}.AEO_SKILL_STAGE/{skill_name}"
            for root, _, files in os.walk(zip_extract_dir):
                for fname in files:
                    local_path = os.path.join(root, fname)
                    rel_dir = os.path.relpath(root, zip_extract_dir)
                    stage_path = (
                        f"{stage_base}/"
                        if rel_dir == "."
                        else f"{stage_base}/{rel_dir}/"
                    )
                    try:
                        session.file.put(local_path, stage_path, auto_compress=False, overwrite=True)
                    except Exception as _e:
                        st.warning(f"Could not upload {fname} to stage (non-blocking): {_e}")
        else:
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
        if zip_extract_dir and os.path.exists(zip_extract_dir):
            shutil.rmtree(zip_extract_dir, ignore_errors=True)

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

                if model in CORTEX_NATIVE_MODELS:
                    native_model = CORTEX_NATIVE_MODELS[model]
                    # Use cortex --print with skill content prepended as context
                    if is_zip:
                        _native_prompt = (
                            f"[SKILL CONTEXT — entry point]\n{skill_content}\n\n"
                            f"[NOTE: Sub-skills from this suite are available on the skill "
                            f"stage under '{skill_name}/' and can be referenced by name.]\n\n"
                            f"[QUESTION]\n{q_text}"
                        )
                    else:
                        _native_prompt = (
                            f"[SKILL CONTEXT]\n{skill_content}\n\n"
                            f"[QUESTION]\n{q_text}"
                        )
                    _cortex_bin = shutil.which("cortex")
                    if not IS_SIS:
                        # Local: run cortex CLI directly
                        try:
                            _native_result = subprocess.run(
                                [_cortex_bin or "cortex", "--print", _native_prompt,
                                 "--model", native_model, "--connection", "my-snowflake"],
                                capture_output=True, text=True, timeout=60,
                            )
                            response_text = _native_result.stdout.strip() if _native_result.returncode == 0 else f"[Error: {_native_result.stderr.strip()}]"
                        except subprocess.TimeoutExpired:
                            response_text = "[Error: cortex --print timed out]"
                        except Exception as _e:
                            response_text = f"[Error: {_e}]"
                    else:
                        # SiS: trigger SPCS job with native Cortex Code CLI
                        st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ **{qid}**: Running CoCo ({native_model}) via :blue[SPCS]")
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
                baseline = get_baseline_scores(qid, get_baseline_run_id(model))

                run_write(
                    """
                    INSERT INTO AEO_SKILL_TESTS
                        (TEST_ID, USER_NAME, SKILL_NAME,
                         QUESTION_ID, QUESTION_TEXT, CATEGORY, MODEL, RESPONSE_TEXT,
                         CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE,
                         RECOMMENDATION, TOTAL_SCORE, MUST_HAVE_PASS,
                         JUDGE_DETAILS,
                         CANONICAL_ANSWER,
                         MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5)
                    SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           PARSE_JSON(?),
                           ?, ?, ?, ?, ?, ?
                    """,
                    params=[
                        str(uuid.uuid4()), user_name, skill_name,
                        qid, q_text, category, model,
                        response_text,
                        avg["correctness"], avg["completeness"], avg["recency"],
                        avg["citation"], avg["recommendation"],
                        avg["total"], avg["must_have_pass"],
                        json.dumps(panel_result["judges"], default=str),
                        canonical,
                        must_haves[0] if len(must_haves) > 0 else None,
                        must_haves[1] if len(must_haves) > 1 else None,
                        must_haves[2] if len(must_haves) > 2 else None,
                        must_haves[3] if len(must_haves) > 3 else None,
                        must_haves[4] if len(must_haves) > 4 else None,
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
                if baseline_results:
                    if single_q:
                        bl = baseline_results[0]["baseline"]
                    else:
                        bl = {d: sum(r["baseline"][d] for r in baseline_results) / len(baseline_results)
                              for d in dims + ["total", "must_have_pass"]}
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

                if single_q:
                    item = results[0]
                    with st.expander("Generated response"):
                        st.markdown(item["response_text"])
                    citation_expander(item["response_text"])
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

                # ---- HTML export ----
                import html as _html_mod_live

                st.divider()

                def _make_live_html(
                    _model=model, _results=results, _avg=avg, _bl=bl,
                    _single_q=single_q, _dims=dims, _dim_labels=dim_labels,
                    _skill_n=skill_name, _cat_n=category,
                    _score_pct=score_pct, _fig=fig,
                ):
                    _chart_div = _fig.to_html(include_plotlyjs="cdn", full_html=False)
                    _mh_pct_str = f"{_avg['must_have_pass']:.0%}"
                    _body = ""

                    if _single_q:
                        _item = _results[0]
                        _resp_txt = _html_mod_live.escape(_item["response_text"] or "")
                        _ca_txt = _html_mod_live.escape(
                            _item.get("canonical") or "Not captured for this run."
                        )
                        _body += (
                            f'<div class="section-title">Generated Response</div>'
                            f'<div class="text-block">{_resp_txt}</div>'
                            f'<div class="section-title">Canonical Answer (Ground Truth)</div>'
                            f'<div class="text-block">{_ca_txt}</div>'
                        )
                        _mhs_active = [m for m in (_item.get("must_haves") or []) if m]
                        if _mhs_active:
                            _jd = _item["panel_result"]["judges"]
                            _mh_body = ""
                            for _mi, _mh in enumerate(_mhs_active, 1):
                                _votes = [
                                    s["must_have"][_mi - 1]
                                    for s in (_jd or {}).values()
                                    if not s.get("error") and len(s.get("must_have", [])) >= _mi
                                ]
                                _icon = "&#10003;" if _votes and all(_votes) else ("&#9888;" if any(_votes) else "&#10007;")
                                _mh_body += f'<div class="mh-item">{_icon} <strong>{_mi}.</strong> {_html_mod_live.escape(_mh)}</div>\n'
                            _body += (
                                f'<div class="section-title">Must-Have Criteria</div>'
                                f'<div class="mh-list">{_mh_body}</div>'
                            )
                        _jd2 = _item["panel_result"]["judges"]
                        if _jd2:
                            _jbody = ""
                            for _jname, _jsc in _jd2.items():
                                _jbody += f'<div class="judge"><strong>{_html_mod_live.escape(_jname)}</strong>'
                                if "error" in _jsc:
                                    _jbody += f'<span style="color:#f66"> Error: {_html_mod_live.escape(str(_jsc["error"]))}</span>'
                                else:
                                    _jbody += '<div class="judge-scores">'
                                    for _dl, _dk in zip(_dim_labels, _dims):
                                        _jbody += (
                                            f'<div class="judge-score">'
                                            f'<div class="judge-score-label">{_dl}</div>'
                                            f'<div class="judge-score-val">{_jsc.get(_dk, "-")}</div>'
                                            f'</div>'
                                        )
                                    _jbody += '</div>'
                                _jbody += '</div>'
                            _body += f'<div class="section-title">Per-Judge Breakdown</div>{_jbody}'
                    else:
                        _tbl = (
                            '<table style="width:100%;border-collapse:collapse;font-size:.85em">'
                            '<tr style="background:#1a1a2e">'
                        )
                        for _th in ["Question", "Score %", "Correctness", "Completeness",
                                    "Recency", "Citation", "Recommendation", "MH Pass"]:
                            _tbl += f'<th style="text-align:left;padding:6px 10px;border-bottom:1px solid #333">{_th}</th>'
                        _tbl += '</tr>'
                        for _r in _results:
                            _qp = _r["avg"]["total"] / 50.0 * 100
                            _tbl += '<tr style="border-bottom:1px solid #222">'
                            _tbl += f'<td style="padding:6px 10px">{_html_mod_live.escape(str(_r["QUESTION_ID"]))}</td>'
                            _tbl += f'<td style="padding:6px 10px">{_qp:.1f}%</td>'
                            for _dk in _dims:
                                _tbl += f'<td style="padding:6px 10px">{_r["avg"][_dk]:.1f}</td>'
                            _tbl += f'<td style="padding:6px 10px">{_r["avg"]["must_have_pass"]*100:.0f}%</td>'
                            _tbl += '</tr>'
                        _tbl += '</table>'
                        _body += f'<div class="section-title">Question Scores</div>{_tbl}'

                    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AEO Skill Test: {_html_mod_live.escape(_skill_n)}</title>
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
<h1>AEO Skill Test: {_html_mod_live.escape(_skill_n)}</h1>
<div class="meta">Category: <strong>{_html_mod_live.escape(_cat_n)}</strong> &middot; Model: <strong>{_html_mod_live.escape(_model)}</strong></div>
<div class="metrics">
  <div><div class="metric-label">Overall Score</div><div class="metric-value">{_score_pct:.1f}%</div></div>
  <div><div class="metric-label">Total (raw)</div><div class="metric-value">{_avg['total']:.1f} / 50</div></div>
  <div><div class="metric-label">Must-Have Pass</div><div class="metric-value">{_mh_pct_str}</div></div>
</div>
<div class="section-title">Dimension Scores</div>
{_chart_div}
{_body}
<footer>Exported from AEO Benchmark Dashboard</footer>
</body>
</html>"""

                _html_bytes = _make_live_html().encode("utf-8")
                _export_fname = f"aeo_{skill_name}_{category}_{model}.html".replace(" ", "_")
                st.download_button(
                    "Download as HTML",
                    data=_html_bytes,
                    file_name=_export_fname,
                    mime="text/html",
                    key=f"dl_live_{model}",
                )

# --- History ---
st.divider()
with st.expander("Skill test history", expanded=True):
    st.caption(f"Results are written to `{DB}.{SCH}.AEO_SKILL_TESTS`")

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

        # Run selector for replay
        st.divider()
        _run_labels = [
            f"{row['CREATED_AT']} · {row['SKILL_NAME']} · {row['CATEGORY']} · {row['MODEL']}"
            for _, row in history_df.iterrows()
        ]
        _run_keys = {
            label: (row["SKILL_NAME"], row["CATEGORY"], row["MODEL"], row["CREATED_AT"])
            for label, (_, row) in zip(_run_labels, history_df.iterrows())
        }
        _sel_label = st.selectbox(
            "View a past run in full detail",
            ["— select a run —"] + _run_labels,
            key="history_replay_selectbox",
        )
        if _sel_label != "— select a run —":
            st.session_state["replay_run_key"] = _run_keys[_sel_label]
        else:
            st.session_state["replay_run_key"] = None

# --- Replay loaded run ---
_replay = st.session_state.get("replay_run_key")
if _replay:
    _skill_n, _cat_n, _model_n, _ts_n = _replay
    st.divider()
    with st.container(border=True):
        st.subheader(f"Loaded run: {_skill_n}")
        st.caption(f"Category: **{_cat_n}** · Model: **{_model_n}** · {_ts_n}")

        _session = get_session()
        _ts_str = pd.Timestamp(_ts_n).strftime('%Y-%m-%d %H:%M:%S.%f')
        _has_new_cols = True
        _detail_rows = pd.DataFrame()

        # First attempt: full column set including new canonical/must-have columns
        try:
            _detail_rows = _session.sql(
                f"""
                SELECT QUESTION_ID, QUESTION_TEXT, RESPONSE_TEXT,
                       CANONICAL_ANSWER,
                       MUST_HAVE_1, MUST_HAVE_2, MUST_HAVE_3, MUST_HAVE_4, MUST_HAVE_5,
                       CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE, RECOMMENDATION,
                       TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS
                FROM AEO_SKILL_TESTS
                WHERE SKILL_NAME = ? AND CATEGORY = ? AND MODEL = ?
                  AND DATE_TRUNC('second', CREATED_AT) = DATE_TRUNC('second', '{_ts_str}'::TIMESTAMP_NTZ)
                ORDER BY QUESTION_ID
                """,
                params=[_skill_n, _cat_n, _model_n],
            ).to_pandas()
        except Exception as _e1:
            # If failure is due to missing new columns, fall back to base columns only
            if any(c in str(_e1).upper() for c in ["CANONICAL_ANSWER", "MUST_HAVE_1", "INVALID IDENTIFIER"]):
                _has_new_cols = False
                st.info(
                    "This run predates the canonical answer and must-have capture feature. "
                    "Canonical answer and must-have criteria are not available for this run."
                )
                try:
                    _detail_rows = _session.sql(
                        f"""
                        SELECT QUESTION_ID, QUESTION_TEXT, RESPONSE_TEXT,
                               NULL AS CANONICAL_ANSWER,
                               NULL AS MUST_HAVE_1, NULL AS MUST_HAVE_2, NULL AS MUST_HAVE_3,
                               NULL AS MUST_HAVE_4, NULL AS MUST_HAVE_5,
                               CORRECTNESS, COMPLETENESS, RECENCY, CITATION_SCORE, RECOMMENDATION,
                               TOTAL_SCORE, MUST_HAVE_PASS, JUDGE_DETAILS
                        FROM AEO_SKILL_TESTS
                        WHERE SKILL_NAME = ? AND CATEGORY = ? AND MODEL = ?
                          AND DATE_TRUNC('second', CREATED_AT) = DATE_TRUNC('second', '{_ts_str}'::TIMESTAMP_NTZ)
                        ORDER BY QUESTION_ID
                        """,
                        params=[_skill_n, _cat_n, _model_n],
                    ).to_pandas()
                except Exception as _e2:
                    st.error(f"Could not load run detail: {_e2}")
            else:
                st.error(f"Could not load run detail: {_e1}")

        if _detail_rows.empty:
            # Check whether any data exists for this skill at all to give a precise message
            try:
                _exists = _session.sql(
                    "SELECT COUNT(*) AS CNT FROM AEO_SKILL_TESTS WHERE SKILL_NAME = ? AND CATEGORY = ? AND MODEL = ?",
                    params=[_skill_n, _cat_n, _model_n],
                ).to_pandas()
                _cnt = int(_exists["CNT"].iloc[0]) if not _exists.empty else 0
            except Exception:
                _cnt = -1

            if _cnt == 0:
                st.warning(
                    f"No rows found for skill **{_skill_n}** / category **{_cat_n}** / model **{_model_n}**. "
                    "The run data may have been deleted."
                )
            elif _cnt > 0:
                st.warning(
                    f"Found {_cnt} row(s) for this skill and model but none matched the exact timestamp "
                    f"({_ts_str}). The run may have been stored with a slightly different timestamp."
                )
            else:
                st.warning("No detail rows found for this run.")
        else:
            _dims = ["correctness", "completeness", "recency", "citation", "recommendation"]
            _dim_labels = ["Correctness", "Completeness", "Recency", "Citation", "Recommendation"]
            _dim_cols = ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]
            _n_q = len(_detail_rows)
            _single_q = (_n_q == 1)

            _avg_total = _detail_rows["TOTAL_SCORE"].mean()
            _avg_mh = _detail_rows["MUST_HAVE_PASS"].mean()
            _score_pct = _avg_total / 50.0 * 100

            _m1, _m2, _m3 = st.columns(3)
            _m1.metric("Overall Score", f"{_score_pct:.1f}%")
            _m2.metric("Total (raw)", f"{_avg_total:.1f} / 50")
            _m3.metric("Must-Have Pass", f"{_avg_mh:.0%}")

            _skill_dim_avgs = [_detail_rows[col].mean() for col in _dim_cols]
            _bl_dim_lists = []
            for _, _r in _detail_rows.iterrows():
                _bl = get_baseline_scores(_r["QUESTION_ID"], get_baseline_run_id(_model_n))
                if _bl:
                    _bl_dim_lists.append([_bl[d] for d in _dims])

            _fig = go.Figure()
            _fig.add_trace(go.Bar(
                x=_dim_labels, y=_skill_dim_avgs,
                name=_model_n, marker_color="#29B5E8",
            ))
            if _bl_dim_lists:
                _bl_means = [
                    sum(r[i] for r in _bl_dim_lists) / len(_bl_dim_lists)
                    for i in range(len(_dims))
                ]
                _fig.add_trace(go.Bar(
                    x=_dim_labels, y=_bl_means,
                    name=f"Baseline ({get_baseline_model(_model_n)})", marker_color="#888888", opacity=0.7,
                ))
            _fig.update_layout(
                barmode="group",
                yaxis=dict(range=[0, 10], title="Score (1-10)"),
                height=350,
                margin=dict(t=10, b=0, l=0, r=0),
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(_fig, use_container_width=True)

            if _single_q:
                _r = _detail_rows.iloc[0]
                with st.expander("Generated response"):
                    st.markdown(_r["RESPONSE_TEXT"] or "")
                citation_expander(_r["RESPONSE_TEXT"] or "")
                with st.expander("Canonical answer (ground truth)"):
                    _ca = _r.get("CANONICAL_ANSWER")
                    if _ca:
                        st.markdown(_ca)
                    else:
                        st.caption("Not captured for this run (predates canonical answer storage).")
                _mhs = [_r.get(f"MUST_HAVE_{i}") or "" for i in range(1, 6)]
                _active_mhs = [m for m in _mhs if m]
                if _active_mhs:
                    with st.expander(f"Must-have criteria ({len(_active_mhs)})"):
                        st.caption("✅ All judges passed · ⚠️ Some judges passed (split) · ❌ No judges passed")
                        _jd = _r["JUDGE_DETAILS"]
                        if isinstance(_jd, str):
                            import json as _json
                            _jd = _json.loads(_jd)
                        for _i, _mh in enumerate(_active_mhs, 1):
                            _votes = [
                                s["must_have"][_i - 1]
                                for s in (_jd or {}).values()
                                if not s.get("error") and len(s.get("must_have", [])) >= _i
                            ]
                            _icon = "✅" if _votes and all(_votes) else ("⚠️" if any(_votes) else "❌")
                            st.markdown(f"{_icon} **{_i}.** {_mh}")
                _jd = _r["JUDGE_DETAILS"]
                if isinstance(_jd, str):
                    import json as _json
                    _jd = _json.loads(_jd)
                if _jd:
                    with st.expander("Per-judge breakdown"):
                        for _judge, _scores in _jd.items():
                            st.markdown(f"**{_judge}**")
                            if "error" in _scores:
                                st.error(_scores["error"])
                            else:
                                _jcols = st.columns(5)
                                for _ji, _dl in enumerate(_dim_labels):
                                    _jcols[_ji].metric(_dl, f"{_scores[_dims[_ji]]:.1f}")
            else:
                _all_rows = []
                for _, _r in _detail_rows.iterrows():
                    _q_pct = _r["TOTAL_SCORE"] / 50.0 * 100
                    _bl = get_baseline_scores(_r["QUESTION_ID"], get_baseline_run_id(_model_n))
                    _delta = (_q_pct - _bl["total"] / 50.0 * 100) if _bl else None
                    _all_rows.append({
                        "Question": _r["QUESTION_ID"],
                        "Score %": round(_q_pct, 1),
                        "Delta (pp)": round(_delta, 1) if _delta is not None else None,
                        "Correctness": round(_r["CORRECTNESS"], 1),
                        "Completeness": round(_r["COMPLETENESS"], 1),
                        "Recency": round(_r["RECENCY"], 1),
                        "Citation": round(_r["CITATION_SCORE"], 1),
                        "Recommendation": round(_r["RECOMMENDATION"], 1),
                        "MH Pass": round(_r["MUST_HAVE_PASS"] * 100, 1),
                    })
                st.dataframe(
                    pd.DataFrame(_all_rows),
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
                _fig_radar = go.Figure()
                _fig_radar.add_trace(go.Scatterpolar(
                    r=_skill_dim_avgs + [_skill_dim_avgs[0]],
                    theta=_dim_labels + [_dim_labels[0]],
                    fill="toself", name=_model_n, line_color="#29B5E8",
                ))
                if _bl_dim_lists:
                    _bl_means = [
                        sum(r[i] for r in _bl_dim_lists) / len(_bl_dim_lists)
                        for i in range(len(_dims))
                    ]
                    _fig_radar.add_trace(go.Scatterpolar(
                        r=_bl_means + [_bl_means[0]],
                        theta=_dim_labels + [_dim_labels[0]],
                        fill="toself", name="Baseline",
                        line_color="#888888", opacity=0.5,
                    ))
                _fig_radar.update_layout(
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
                st.plotly_chart(_fig_radar, use_container_width=True)

            # ---- HTML export ----
            import html as _html_mod

            st.divider()

            def _make_export_html():
                import json as _json_ex
                _chart_div = _fig.to_html(include_plotlyjs="cdn", full_html=False)
                _mh_pct_str = f"{_avg_mh:.0%}"
                _body = ""

                if _single_q:
                    _row = _detail_rows.iloc[0]
                    _resp_txt = _html_mod.escape(_row.get("RESPONSE_TEXT") or "")
                    _ca_txt = _html_mod.escape(
                        _row.get("CANONICAL_ANSWER") or "Not captured for this run."
                    )
                    _body += (
                        f'<div class="section-title">Generated Response</div>'
                        f'<div class="text-block">{_resp_txt}</div>'
                        f'<div class="section-title">Canonical Answer (Ground Truth)</div>'
                        f'<div class="text-block">{_ca_txt}</div>'
                    )
                    _mhs_list = [_row.get(f"MUST_HAVE_{i}") or "" for i in range(1, 6)]
                    _mhs_active = [m for m in _mhs_list if m]
                    if _mhs_active:
                        _jd_raw = _row.get("JUDGE_DETAILS")
                        if isinstance(_jd_raw, str):
                            _jd_raw = _json_ex.loads(_jd_raw)
                        _mh_body = ""
                        for _mi, _mh in enumerate(_mhs_active, 1):
                            _votes = [
                                s["must_have"][_mi - 1]
                                for s in (_jd_raw or {}).values()
                                if not s.get("error") and len(s.get("must_have", [])) >= _mi
                            ]
                            _icon = "&#10003;" if _votes and all(_votes) else ("&#9888;" if any(_votes) else "&#10007;")
                            _mh_body += f'<div class="mh-item">{_icon} <strong>{_mi}.</strong> {_html_mod.escape(_mh)}</div>\n'
                        _body += (
                            f'<div class="section-title">Must-Have Criteria</div>'
                            f'<div class="mh-list">{_mh_body}</div>'
                        )
                    _jd_raw2 = _row.get("JUDGE_DETAILS")
                    if isinstance(_jd_raw2, str):
                        _jd_raw2 = _json_ex.loads(_jd_raw2)
                    if _jd_raw2:
                        _jbody = ""
                        for _jname, _jsc in _jd_raw2.items():
                            _jbody += f'<div class="judge"><strong>{_html_mod.escape(_jname)}</strong>'
                            if "error" in _jsc:
                                _jbody += f'<span style="color:#f66"> Error: {_html_mod.escape(str(_jsc["error"]))}</span>'
                            else:
                                _jbody += '<div class="judge-scores">'
                                for _dl, _dk in zip(_dim_labels, _dims):
                                    _jbody += (
                                        f'<div class="judge-score">'
                                        f'<div class="judge-score-label">{_dl}</div>'
                                        f'<div class="judge-score-val">{_jsc.get(_dk, "-")}</div>'
                                        f'</div>'
                                    )
                                _jbody += '</div>'
                            _jbody += '</div>'
                        _body += f'<div class="section-title">Per-Judge Breakdown</div>{_jbody}'
                else:
                    _tbl = (
                        '<table style="width:100%;border-collapse:collapse;font-size:.85em">'
                        '<tr style="background:#1a1a2e">'
                    )
                    for _th in ["Question", "Score %", "Correctness", "Completeness",
                                "Recency", "Citation", "Recommendation", "MH Pass"]:
                        _tbl += f'<th style="text-align:left;padding:6px 10px;border-bottom:1px solid #333">{_th}</th>'
                    _tbl += '</tr>'
                    for _, _rr in _detail_rows.iterrows():
                        _qp = _rr["TOTAL_SCORE"] / 50.0 * 100
                        _tbl += '<tr style="border-bottom:1px solid #222">'
                        _tbl += f'<td style="padding:6px 10px">{_html_mod.escape(str(_rr["QUESTION_ID"]))}</td>'
                        _tbl += f'<td style="padding:6px 10px">{_qp:.1f}%</td>'
                        for _dc in ["CORRECTNESS", "COMPLETENESS", "RECENCY", "CITATION_SCORE", "RECOMMENDATION"]:
                            _tbl += f'<td style="padding:6px 10px">{_rr[_dc]:.1f}</td>'
                        _tbl += f'<td style="padding:6px 10px">{_rr["MUST_HAVE_PASS"]*100:.0f}%</td>'
                        _tbl += '</tr>'
                    _tbl += '</table>'
                    _body += f'<div class="section-title">Question Scores</div>{_tbl}'

                return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AEO Skill Test: {_html_mod.escape(_skill_n)}</title>
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
<h1>AEO Skill Test: {_html_mod.escape(_skill_n)}</h1>
<div class="meta">Category: <strong>{_html_mod.escape(_cat_n)}</strong> &middot; Model: <strong>{_html_mod.escape(_model_n)}</strong> &middot; {_html_mod.escape(str(_ts_n))}</div>
<div class="metrics">
  <div><div class="metric-label">Overall Score</div><div class="metric-value">{_score_pct:.1f}%</div></div>
  <div><div class="metric-label">Total (raw)</div><div class="metric-value">{_avg_total:.1f} / 50</div></div>
  <div><div class="metric-label">Must-Have Pass</div><div class="metric-value">{_mh_pct_str}</div></div>
</div>
<div class="section-title">Dimension Scores</div>
{_chart_div}
{_body}
<footer>Exported from AEO Benchmark Dashboard</footer>
</body>
</html>"""

            _html_bytes = _make_export_html().encode("utf-8")
            _export_fname = f"aeo_{_skill_n}_{_cat_n}_{_model_n}.html".replace(" ", "_")
            st.download_button(
                "Download as HTML",
                data=_html_bytes,
                file_name=_export_fname,
                mime="text/html",
            )
