"""
fig_04_tool_usage.py
Agentic run observability: tool call breakdown and generation time vs score.
Two-panel figure for the AEO whitepaper.
Data from V3_AEO_TRANSCRIPT and V3_AEO_SCORES (claude-opus-4-6 agentic configs).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ---------------------------------------------------------------------------
# Data (from Snowflake queries on CHANINN_DEMO_DATA.APPS.V3_AEO_TRANSCRIPT
# and V3_AEO_SCORES, connection: devrel, 2026-04-29)
# Sorted by score descending.
# ---------------------------------------------------------------------------

CONFIGS = [
    "C+A",
    "D+C+A",
    "A",
    "D+A",
    "D+A+S",
    "D+C+A+S",
    "A+S",
    "C+A+S",
]

SCORES = [69.2, 67.4, 62.6, 62.6, 58.1, 57.5, 57.5, 57.4]
GEN_SECS = [52.3, 50.2, 54.2, 48.1, 103.4, 117.1, 108.6, 118.1]

# Average tool calls per question (nulls treated as 0)
TOOLS = {
    "bash":        [0.20, 0.08, 0.13, 0.09, 0.56, 0.52, 0.46, 0.49],
    "read":        [0.91, 0.74, 0.96, 0.75, 0.82, 0.98, 1.07, 1.06],
    "web search":  [0.66, 0.24, 0.15, 0.08, 1.01, 1.41, 1.08, 1.30],
    "web fetch":   [0.09, 0.02, 0.00, 0.02, 0.08, 0.21, 0.04, 0.21],
    "sql execute": [0.05, 0.02, 0.06, 0.02, 0.01, 0.02, 0.00, 0.01],
    "skill":       [0.58, 0.45, 0.65, 0.46, 0.39, 0.49, 0.46, 0.49],
    "glob":        [0.08, 0.03, 0.09, 0.03, 0.09, 0.14, 0.08, 0.11],
    "other":       [0.05, 0.05, 0.27, 0.09, 0.03, 0.09, 0.03, 0.03],
}

# Self-critique flag per config (same order as CONFIGS)
HAS_SC = [False, False, False, False, True, True, True, True]

# ---------------------------------------------------------------------------
# Colour palette (Snowflake brand + complementary)
# ---------------------------------------------------------------------------
TOOL_COLORS = {
    "read":        "#29B5E8",  # Snowflake blue
    "skill":       "#52B788",  # green
    "web search":  "#FF9F36",  # orange
    "web fetch":   "#F0B429",  # amber
    "bash":        "#1A56A0",  # dark blue
    "glob":        "#A8DADC",  # teal
    "sql execute": "#7D44CF",  # purple
    "other":       "#CCCCCC",  # grey
}

BLUE   = "#29B5E8"
ORANGE = "#FF9F36"

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
fig, (ax_bars, ax_scatter) = plt.subplots(
    1, 2,
    figsize=(13, 5.8),
    gridspec_kw={"width_ratios": [1.6, 1]},
)
fig.patch.set_facecolor("white")

n = len(CONFIGS)
y = np.arange(n)
bar_height = 0.65

# ---------------------------------------------------------------------------
# Panel A: horizontal stacked bar chart
# ---------------------------------------------------------------------------
ax_bars.set_facecolor("#F8F9FA")
for spine in ax_bars.spines.values():
    spine.set_visible(False)
ax_bars.tick_params(left=False, bottom=False)
ax_bars.xaxis.grid(True, color="white", linewidth=1.2, zorder=0)
ax_bars.set_axisbelow(True)

lefts = np.zeros(n)
for tool, vals in TOOLS.items():
    vals = np.array(vals)
    bars = ax_bars.barh(
        y, vals, left=lefts, height=bar_height,
        color=TOOL_COLORS[tool], label=tool, zorder=3,
    )
    lefts += vals

# Score annotations at the right end of each bar
for i, (score, total) in enumerate(zip(SCORES, lefts)):
    ax_bars.text(
        total + 0.04, i, f"{score:.1f}%",
        va="center", ha="left", fontsize=8.5, color="#333333",
        fontweight="bold",
    )

ax_bars.set_yticks(y)
ax_bars.set_yticklabels(CONFIGS, fontsize=9)
ax_bars.set_xlabel("Avg tool calls per question", fontsize=9, labelpad=6)
ax_bars.set_xlim(0, lefts.max() + 0.7)
ax_bars.set_ylim(-0.55, n - 0.45)
ax_bars.invert_yaxis()  # highest score at top

# Divider between non-SC (top 4) and SC (bottom 4)
ax_bars.axhline(3.5, color="#888888", linewidth=0.8, linestyle="--", zorder=4)
ax_bars.text(
    0.01, 3.35, "without self-critique",
    transform=ax_bars.get_yaxis_transform(),
    fontsize=7.5, color="#555555", va="bottom",
)
ax_bars.text(
    0.01, 3.65, "with self-critique",
    transform=ax_bars.get_yaxis_transform(),
    fontsize=7.5, color="#555555", va="top",
)

ax_bars.set_title("(a) Tool calls per question by agentic configuration",
                  fontsize=10, pad=10, loc="left")

# Tool-type legend below panel (a)
tool_handles = [
    mpatches.Patch(color=TOOL_COLORS[t], label=t) for t in TOOLS
]
ax_bars.legend(
    handles=tool_handles,
    loc="upper center",
    bbox_to_anchor=(0.5, -0.14),
    ncol=4,
    fontsize=8,
    framealpha=0.9,
    edgecolor="#cccccc",
)

# ---------------------------------------------------------------------------
# Panel B: scatter — generation time vs score
# ---------------------------------------------------------------------------
ax_scatter.set_facecolor("#F8F9FA")
for spine in ax_scatter.spines.values():
    spine.set_visible(False)
ax_scatter.tick_params(left=False, bottom=False)
ax_scatter.xaxis.grid(True, color="white", linewidth=1.2, zorder=0)
ax_scatter.yaxis.grid(True, color="white", linewidth=1.2, zorder=0)
ax_scatter.set_axisbelow(True)

label_offsets = {
    "C+A":     (4, 3),
    "D+C+A":   (-40, -10),
    "A":       (4, 3),
    "D+A":     (4, -10),
    "D+A+S":   (4, 3),
    "D+C+A+S": (-54, 3),
    "A+S":     (4, -10),
    "C+A+S":   (4, 3),
}

for cfg, score, secs, sc in zip(CONFIGS, SCORES, GEN_SECS, HAS_SC):
    color  = ORANGE if sc else BLUE
    marker = "s" if sc else "o"
    ax_scatter.scatter(secs, score, color=color, marker=marker,
                       s=72, zorder=5, edgecolors="white", linewidths=0.8)
    dx, dy = label_offsets.get(cfg, (4, 3))
    ax_scatter.annotate(
        cfg, xy=(secs, score),
        xytext=(dx, dy), textcoords="offset points",
        fontsize=7.5, color="#333333",
    )

ax_scatter.set_xlabel("Avg generation time (seconds)", fontsize=9, labelpad=6)
ax_scatter.set_ylabel("Score %", fontsize=9, labelpad=6)
ax_scatter.set_title("(b) Generation time vs score",
                     fontsize=10, pad=10, loc="left")

# Self-critique legend below panel (b)
sc_handles = [
    mpatches.Patch(color=BLUE,   label="Self-critique OFF"),
    mpatches.Patch(color=ORANGE, label="Self-critique ON"),
]
ax_scatter.legend(
    handles=sc_handles,
    loc="upper center",
    bbox_to_anchor=(0.5, -0.14),
    ncol=2,
    fontsize=8,
    framealpha=0.9,
    edgecolor="#cccccc",
)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
plt.tight_layout(pad=2.0)
plt.subplots_adjust(bottom=0.22)
out_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "assets", "fig_04_tool_usage.png",
)
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
