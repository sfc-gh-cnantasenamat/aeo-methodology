"""Shared UI helpers for the AEO benchmark dashboard."""
import re
import streamlit as st
from utils.db import run_query, ENV, V3_MODEL_LABELS, v3_models_sql, snowhouse_models_sql


def citation_expander(response_text: str) -> None:
    """Render a collapsible expander listing URLs extracted from the response.

    Extracts both markdown-style links ([label](url)) and bare https:// URLs.
    Shows a note explaining low Citation scores when no sources are found.
    """
    # Markdown links: [label](url)
    md_links = re.findall(r'\[([^\]]+)\]\((https?://[^\s\)]+)\)', response_text or "")
    md_urls = {url for _, url in md_links}
    # Bare URLs not already captured inside a markdown link
    all_urls = re.findall(r'https?://[^\s\)\]\'"<>]+', response_text or "")
    bare = [(url, url) for url in all_urls if url not in md_urls]

    # Merge, deduplicate by URL, preserve order
    seen: set = set()
    citations: list = []
    for label, url in md_links + bare:
        if url not in seen:
            seen.add(url)
            citations.append((label, url))

    count = len(citations)
    header = f"Citations ({count})" if count else "Citations (none found)"
    with st.expander(header):
        if citations:
            for label, url in citations:
                display = label if label != url else url
                st.markdown(f"- [{display}]({url})")
        else:
            st.caption(
                "No citation sources (URLs) were found in the response. "
                "This typically explains a low Citation score."
            )


def model_selector(key: str = "model_sel") -> tuple[str, str]:
    """Render a segmented_control for model selection and return (label, model_id).

    On DevRel the model list comes from V3_AEO_SCORES RUN_IDs.
    On Snowhouse the model list comes from AEO_RUNS.

    Returns:
        (friendly_label, model_id) e.g. ("Opus 4.6", "claude-opus-4-6")
    """
    if ENV == "devrel":
        _df = run_query(v3_models_sql())
    else:
        _df = run_query(snowhouse_models_sql())
    _models = _df["MODEL"].tolist()

    _labels = [V3_MODEL_LABELS.get(m, m) for m in _models]
    _label_to_model = {V3_MODEL_LABELS.get(m, m): m for m in _models}

    _sel = st.segmented_control(
        "Generation model",
        options=_labels,
        default=_labels[0] if _labels else None,
        key=key,
    )
    _sel = _sel or (_labels[0] if _labels else "")
    return _sel, _label_to_model.get(_sel, _models[0] if _models else "")
