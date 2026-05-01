"""
fig_05_rankings_heatmap.py
Rankings heatmap: 16 configurations x 3 models for Score% and MH%.
Replaces the 16-run rankings table in the Results section.
Data from V3_AEO_SCORES (connection: devrel, 2026-04-29).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
import numpy as np
import os

# ---------------------------------------------------------------------------
# Data — sorted by claude-opus-4-6 score descending
# ---------------------------------------------------------------------------

CONFIGS = [
    'CA', 'DCA', 'A', 'DA', 'DAS', 'AS', 'DCAS', 'CAS',
    'DCS', 'C', 'base', 'D', 'DS', 'DC', 'CS', 'S',
]
CONFIG_LABELS = [
    'C+A', 'D+C+A', 'A', 'D+A', 'D+A+S', 'A+S', 'D+C+A+S', 'C+A+S',
    'D+C+S', 'C', 'Baseline', 'D', 'D+S', 'D+C', 'C+S', 'S',
]
MODEL_LABELS = ['opus-4-6', 'opus-4-7', 'gpt-5.4']

# Factor flags [D, C, A, S] per config row
FLAG_DATA = [
    [0, 1, 1, 0],  # CA
    [1, 1, 1, 0],  # DCA
    [0, 0, 1, 0],  # A
    [1, 0, 1, 0],  # DA
    [1, 0, 1, 1],  # DAS
    [0, 0, 1, 1],  # AS
    [1, 1, 1, 1],  # DCAS
    [0, 1, 1, 1],  # CAS
    [1, 1, 0, 1],  # DCS
    [0, 1, 0, 0],  # C
    [0, 0, 0, 0],  # base
    [1, 0, 0, 0],  # D
    [1, 0, 0, 1],  # DS
    [1, 1, 0, 0],  # DC
    [0, 1, 0, 1],  # CS
    [0, 0, 0, 1],  # S
]

# Score% [opus-4-6, opus-4-7, gpt-5.4]
SCORE_DATA = [
    [69.2, 83.3, 77.2],
    [67.4, 80.6, 72.6],
    [62.6, 68.2, 62.7],
    [62.6, 71.5, 66.8],
    [58.1, 66.6, 64.9],
    [57.5, 67.6, 64.4],
    [57.5, 72.8, 65.1],
    [57.4, 74.9, 65.8],
    [54.0, 64.4, 57.5],
    [53.7, 64.3, 57.1],
    [53.6, 64.1, 57.7],
    [52.9, 64.0, 56.7],
    [52.8, 64.1, 57.0],
    [52.7, 64.1, 57.6],
    [52.6, 64.0, 57.2],
    [52.3, 63.7, 56.2],
]

# Must-Have% [opus-4-6, opus-4-7, gpt-5.4]
MH_DATA = [
    [72.4, 83.3, 72.5],
    [73.7, 83.2, 73.3],
    [74.7, 84.8, 72.8],
    [75.5, 86.1, 74.9],
    [63.1, 74.7, 74.4],
    [63.2, 78.8, 74.6],
    [59.8, 73.6, 73.6],
    [59.9, 74.9, 73.6],
    [58.9, 79.9, 64.2],
    [58.3, 79.3, 63.0],
    [58.9, 81.1, 63.8],
    [58.7, 78.8, 64.1],
    [58.2, 80.7, 64.7],
    [58.9, 79.4, 65.4],
    [57.4, 80.5, 64.3],
    [57.1, 78.3, 62.2],
]

score_arr = np.array(SCORE_DATA)
mh_arr    = np.array(MH_DATA)
flag_arr  = np.array(FLAG_DATA, dtype=float)

n_rows = len(CONFIGS)
VMIN, VMAX = 50, 90

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(14, 9.5))
fig.patch.set_facecolor("white")

gs = gridspec.GridSpec(
    1, 3,
    width_ratios=[0.75, 2.6, 2.6],
    wspace=0.06,
    left=0.09, right=0.98, top=0.91, bottom=0.05,
)
ax_flags = fig.add_subplot(gs[0])
ax_score = fig.add_subplot(gs[1])
ax_mh    = fig.add_subplot(gs[2])


# ---------------------------------------------------------------------------
# Helper: draw heatmap panel
# ---------------------------------------------------------------------------
def draw_heatmap(ax, data, col_labels, title):
    nrows, ncols = data.shape
    ax.imshow(data, aspect="auto", cmap="Blues", vmin=VMIN, vmax=VMAX,
              interpolation="nearest")

    for r in range(nrows):
        for c in range(ncols):
            val = data[r, c]
            norm_val = (val - VMIN) / (VMAX - VMIN)
            text_color = "white" if norm_val > 0.58 else "#333333"
            # Bold the column-best value
            fw = "bold" if val == np.max(data[:, c]) else "normal"
            ax.text(c, r, f"{val:.1f}", ha="center", va="center",
                    fontsize=10, color=text_color, fontweight=fw)

    ax.set_xticks(range(ncols))
    ax.set_xticklabels(col_labels, fontsize=10.5)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.set_yticks(range(nrows))
    ax.set_yticklabels([])
    ax.tick_params(left=False, top=False, bottom=False)
    ax.set_title(title, fontsize=12, pad=22, fontweight="bold")

    # Divider: agentic (rows 0-7) vs non-agentic (rows 8-15)
    ax.axhline(7.5, color="#444444", linewidth=1.0, linestyle="--", zorder=5)

    # Group labels on the right spine
    ax.annotate("agentic", xy=(1.01, 1 - 4/nrows), xycoords="axes fraction",
                fontsize=9, color="#555555", rotation=270, va="center")
    ax.annotate("non-agentic", xy=(1.01, 1 - 12/nrows), xycoords="axes fraction",
                fontsize=9, color="#555555", rotation=270, va="center")

    for spine in ax.spines.values():
        spine.set_visible(False)


# ---------------------------------------------------------------------------
# Panel A: Factor flags
# ---------------------------------------------------------------------------
flag_cmap = mcolors.ListedColormap(["#EFEFEF", "#29B5E8"])
ax_flags.imshow(flag_arr, aspect="auto", cmap=flag_cmap, vmin=0, vmax=1,
                interpolation="nearest")

ax_flags.set_xticks(range(4))
ax_flags.set_xticklabels(["D", "C", "A", "S"], fontsize=10.5)
ax_flags.xaxis.set_ticks_position("top")
ax_flags.xaxis.set_label_position("top")
ax_flags.set_yticks(range(n_rows))
ax_flags.set_yticklabels(CONFIG_LABELS, fontsize=10)
ax_flags.tick_params(left=False, top=False, bottom=False)
ax_flags.set_title("Factors", fontsize=12, pad=22, fontweight="bold")
ax_flags.axhline(7.5, color="#444444", linewidth=1.0, linestyle="--", zorder=5)
for spine in ax_flags.spines.values():
    spine.set_visible(False)

# ---------------------------------------------------------------------------
# Panel B & C: Score and MH heatmaps
# ---------------------------------------------------------------------------
draw_heatmap(ax_score, score_arr, MODEL_LABELS, "Score %")
draw_heatmap(ax_mh,    mh_arr,    MODEL_LABELS, "Must-Have %")

# ---------------------------------------------------------------------------
# Footer: factor key
# ---------------------------------------------------------------------------
fig.text(
    0.09, 0.01,
    "D = Domain Prompt   C = Citation   A = Agentic Tools   S = Self-Critique   "
    "Bold = column best.   Dashed line separates agentic (top) from non-agentic (bottom) configurations.",
    fontsize=9, color="#555555", va="bottom",
)

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
out_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "assets", "fig_05_rankings_heatmap.png",
)
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
print(f"Saved: {out_path}")
