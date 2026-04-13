"""
AEO 2^4 Factorial Heatmap (transposed)
32 categories (rows) x 16 run configs (columns), cells colored by score %.
Rows sorted by C+A (best config) score descending.
Columns: agentic configs first, then non-agentic, each sorted by score desc.
128-question / 32-category dataset.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory
import numpy as np
import os
import textwrap

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# Full category names in alphabetical order (matching data columns)
cat_full_names = [
    'AI Observability & Evaluation',
    'Apache Iceberg Tables',
    'Collaboration & Data Sharing',
    'Cortex AI Function Studio',
    'Cortex AI Functions',
    'Cortex Agents',
    'Cortex Code',
    'Cortex Search',
    'Cost Management',
    'Data Clean Rooms',
    'Data Governance & Security',
    'Data Loading (COPY/Snowpipe)',
    'Data Pipelines (Streams/Tasks)',
    'Data Quality & Observability',
    'Database Change Management',
    'Database Security',
    'Dynamic Tables',
    'Hybrid Tables',
    'Native Apps Framework',
    'Openflow',
    'SQL Performance & Optimization',
    'Semantic Views & Cortex Analyst',
    'Snowflake Fundamentals & Arch.',
    'Snowflake ML',
    'Snowflake Notebooks',
    'Snowflake Postgres',
    'Snowpark',
    'Snowpark Connect & Migration',
    'Snowpark Container Services',
    'Snowsight',
    'Streamlit in Snowflake',
    'dbt Projects on Snowflake',
]

# Score % by category (alphabetical), rows = R1..R16 in Yates order
data = np.array([
    # R1
    [46.3, 69.3, 55.3, 54.7, 43.7, 49.5, 49.8, 59.3, 51.0, 46.5, 66.2, 55.6, 54.5, 54.3, 46.2, 43.0, 57.7, 59.5, 47.8, 26.7, 59.5, 48.8, 62.2, 53.7, 58.3, 38.0, 61.5, 51.3, 66.0, 61.2, 61.3, 42.2],
    # R2
    [47.5, 70.2, 58.2, 61.7, 53.5, 48.3, 52.0, 58.3, 62.2, 61.8, 63.5, 55.2, 64.5, 51.6, 52.5, 62.0, 63.0, 66.7, 47.3, 47.5, 62.3, 52.2, 67.0, 60.5, 60.8, 34.5, 64.3, 51.3, 70.3, 61.3, 73.7, 45.2],
    # R3
    [58.7, 77.8, 77.5, 65.5, 60.2, 66.5, 64.3, 74.0, 70.7, 59.4, 79.7, 68.3, 69.1, 70.8, 62.5, 71.3, 68.3, 73.7, 72.8, 47.3, 72.7, 61.8, 78.7, 62.8, 74.3, 40.0, 72.8, 55.8, 78.0, 71.0, 77.7, 63.7],
    # R4
    [54.2, 75.3, 75.3, 65.5, 64.2, 60.0, 65.8, 70.3, 66.3, 57.2, 76.8, 65.8, 62.1, 68.5, 65.7, 67.8, 65.5, 72.8, 68.7, 53.2, 64.8, 65.7, 72.3, 57.7, 75.3, 43.8, 76.2, 50.3, 74.0, 76.3, 76.5, 62.2],
    # R5
    [69.0, 75.5, 78.2, 73.0, 78.8, 78.5, 83.0, 80.8, 74.7, 69.5, 77.2, 74.3, 65.5, 73.7, 75.8, 76.8, 77.7, 65.5, 74.2, 75.0, 67.3, 70.8, 75.5, 76.2, 70.2, 71.7, 73.0, 74.7, 78.3, 70.5, 79.3, 77.5],
    # R6
    [61.7, 71.8, 70.8, 72.5, 66.7, 73.5, 60.5, 76.3, 67.2, 71.7, 74.3, 68.3, 74.8, 63.5, 68.2, 67.3, 68.5, 62.7, 56.5, 73.8, 67.3, 68.3, 73.8, 66.3, 68.7, 69.2, 72.8, 69.5, 68.7, 72.7, 74.7, 78.7],
    # R7 (best: C+A)
    [80.2, 88.3, 86.8, 84.7, 83.0, 78.5, 88.8, 88.3, 87.5, 79.3, 90.8, 77.2, 81.5, 69.2, 78.0, 84.2, 75.0, 82.8, 82.8, 83.2, 82.7, 79.2, 87.5, 84.3, 80.8, 61.8, 86.2, 81.2, 85.3, 76.8, 86.3, 90.3],
    # R8
    [67.3, 79.8, 73.5, 77.2, 80.7, 71.8, 79.3, 87.7, 68.8, 75.3, 89.0, 81.2, 76.5, 70.5, 71.2, 78.7, 72.2, 69.6, 59.5, 76.3, 83.5, 72.2, 83.3, 79.8, 80.5, 70.7, 78.8, 78.5, 76.0, 80.2, 66.3, 76.3],
    # R9
    [48.7, 65.3, 55.5, 57.3, 51.5, 56.3, 59.8, 59.8, 56.3, 55.5, 64.5, 56.8, 62.8, 58.3, 56.3, 50.2, 60.7, 61.3, 51.8, 40.0, 47.2, 51.8, 53.2, 63.2, 60.5, 41.0, 62.2, 45.8, 67.7, 66.3, 70.7, 35.3],
    # R10
    [55.0, 69.3, 63.0, 57.3, 56.7, 56.0, 53.7, 59.0, 60.5, 57.0, 64.3, 57.3, 65.0, 48.4, 54.7, 61.0, 65.2, 61.5, 55.7, 51.8, 64.3, 51.0, 53.7, 56.5, 60.5, 45.3, 66.5, 51.8, 68.3, 58.8, 67.8, 52.5],
    # R11
    [54.8, 76.5, 77.7, 70.3, 53.8, 65.5, 65.3, 74.8, 68.5, 67.7, 72.2, 69.2, 67.3, 67.5, 63.8, 70.0, 69.7, 76.2, 52.7, 48.7, 64.5, 65.0, 73.3, 71.3, 74.8, 49.0, 70.8, 59.3, 79.3, 73.2, 78.4, 60.7],
    # R12
    [65.2, 74.5, 69.0, 57.2, 63.2, 66.0, 55.2, 76.8, 66.0, 63.0, 75.2, 71.8, 75.0, 69.8, 56.0, 71.5, 64.0, 74.0, 54.0, 45.0, 70.5, 56.5, 71.2, 69.2, 71.7, 50.3, 72.0, 57.0, 78.8, 68.4, 81.2, 56.5],
    # R13
    [52.2, 70.8, 70.0, 73.2, 52.3, 57.8, 63.0, 72.0, 63.3, 56.8, 67.0, 67.5, 64.7, 70.2, 63.3, 72.3, 69.8, 67.2, 67.8, 57.8, 68.0, 69.3, 72.7, 66.5, 65.7, 55.5, 72.8, 69.8, 67.8, 68.8, 74.7, 63.5],
    # R14
    [62.3, 70.5, 68.2, 70.0, 50.8, 47.5, 60.7, 69.8, 63.8, 64.2, 75.3, 66.2, 68.0, 56.3, 65.5, 66.3, 63.0, 75.8, 68.5, 65.8, 62.3, 58.7, 69.2, 62.7, 68.2, 65.7, 72.5, 66.0, 64.2, 68.5, 76.3, 60.5],
    # R15
    [62.5, 83.5, 75.5, 62.9, 66.8, 64.0, 80.7, 82.5, 75.5, 69.5, 83.2, 65.5, 70.0, 73.0, 69.5, 75.2, 75.8, 79.2, 75.3, 64.0, 67.7, 59.3, 78.7, 80.0, 73.0, 48.0, 81.5, 70.2, 80.5, 76.3, 73.8, 74.2],
    # R16
    [62.5, 84.3, 71.7, 84.2, 67.5, 57.3, 82.7, 76.8, 62.0, 71.8, 87.0, 68.2, 80.2, 72.3, 62.8, 73.0, 73.5, 73.7, 72.2, 61.4, 77.3, 77.8, 82.7, 79.5, 78.2, 71.2, 82.8, 73.0, 65.5, 63.7, 84.0, 72.8],
])

# Overall run scores (Yates order)
overall_scores = [53.2, 57.8, 67.7, 66.1, 74.4, 69.4, 82.3, 76.0,
                  56.1, 58.4, 67.2, 66.1, 66.1, 65.4, 72.4, 73.5]

# Short config labels (no run numbers) for column headers
run_configs_short = [
    'Baseline', 'D',    'C',     'D+C',
    'A',        'D+A',  'C+A*',  'D+C+A',
    'S',        'D+S',  'C+S',   'D+C+S',
    'A+S',      'D+A+S','C+A+S', 'D+C+A+S',
]

agentic_flags = [0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1]

# Sort runs: agentic first, then non-agentic; within each group by score desc
sort_key = [(-agentic_flags[i], -overall_scores[i]) for i in range(16)]
sort_idx = sorted(range(16), key=lambda i: sort_key[i])

sorted_data = data[sort_idx]           # (16, 32): runs x categories
col_configs = [run_configs_short[i] for i in sort_idx]
n_agentic = sum(agentic_flags)         # = 8

# --- Transpose: rows = categories, cols = runs ---
data_T = sorted_data.T                 # (32, 16)

# Sort rows (categories) by C+A score (column 0 = best config) descending
ca_col = data_T[:, 0]
cat_sort_idx = np.argsort(-ca_col)
data_T = data_T[cat_sort_idx]
cat_labels = [cat_full_names[i] for i in cat_sort_idx]

# Per-group and overall averages per category
agentic_avg    = data_T[:, :n_agentic].mean(axis=1, keepdims=True)
nonagentic_avg = data_T[:, n_agentic:].mean(axis=1, keepdims=True)
overall_avg    = data_T.mean(axis=1, keepdims=True)
# Layout: [AgAvg | 8 agentic configs | 8 non-agentic configs | NAAvg | Overall]
plot_data = np.hstack([agentic_avg, data_T[:, :n_agentic],
                       data_T[:, n_agentic:], nonagentic_avg, overall_avg])  # (32, 19)
col_labels = ['Avg'] + col_configs[:n_agentic] + col_configs[n_agentic:] + ['Avg', 'Overall\nAvg']

nrows, ncols = plot_data.shape  # 32, 19

# ---- Plot ----
fig, ax = plt.subplots(figsize=(15, 15))

cmap = plt.cm.RdYlGn
im = ax.imshow(plot_data, cmap=cmap, aspect='auto', vmin=25, vmax=95)

# Cell text annotations — avg cols (0, ncols-2, ncols-1) are bold with 1 dp
avg_cols = {0, ncols - 2, ncols - 1}
for i in range(nrows):
    for j in range(ncols):
        val = plot_data[i, j]
        tc = 'white' if val < 38 or val > 88 else 'black'
        fs = 8.5 if j in avg_cols else 7.5
        fw = 'bold' if j in avg_cols else 'normal'
        ax.text(j, i, f'{val:.1f}' if j in avg_cols else f'{val:.0f}',
                ha='center', va='center', fontsize=fs, fontweight=fw, color=tc)

# Vertical separators
ax.axvline(0.5,                    color='black', linewidth=1.5)  # after Agentic Avg
ax.axvline(n_agentic + 0.5,        color='black', linewidth=2.5)  # Agentic / Non-Agentic
ax.axvline(2 * n_agentic + 0.5,    color='black', linewidth=1.5)  # before Non-Agentic Avg
ax.axvline(2 * n_agentic + 1.5,    color='black', linewidth=2.0)  # before Overall Avg

# White grid
for i in range(nrows + 1):
    ax.axhline(i - 0.5, color='white', linewidth=0.4)
sep_js = {0, n_agentic, 2 * n_agentic, 2 * n_agentic + 1}
for j in range(ncols):
    if j not in sep_js:
        ax.axvline(j + 0.5, color='white', linewidth=0.4)

# Row (category) labels on the left — wrapped to max 2 lines
wrapped_labels = ['\n'.join(textwrap.wrap(name, width=20)) for name in cat_labels]
ax.set_yticks(range(nrows))
ax.set_yticklabels(wrapped_labels, fontsize=8.0, linespacing=1.2)

# Column (run config) labels at the top
ax.set_xticks(range(ncols))
ax.set_xticklabels(col_labels, fontsize=8.0, fontfamily='monospace')
ax.tick_params(axis='x', top=True, bottom=False, labeltop=True, labelbottom=False, pad=3)

# Group labels above x-tick labels using blended transform
# (data coords for x centering, axes fraction for y so labels sit outside the axes)
ax.set_ylim(nrows - 0.5, -0.5)
trans = blended_transform_factory(ax.transData, ax.transAxes)
ax.text(n_agentic / 2, 1.022, 'Agentic',
        transform=trans, ha='center', va='bottom',
        fontsize=11, fontweight='bold', color='#2166ac', clip_on=False)
ax.text((3 * n_agentic + 2) / 2, 1.022, 'Non-Agentic',
        transform=trans, ha='center', va='bottom',
        fontsize=11, fontweight='bold', color='#b2182b', clip_on=False)

# Colorbar
cbar = plt.colorbar(im, ax=ax, shrink=0.5, pad=0.01)
cbar.set_label('Score %', fontsize=10)

plt.subplots_adjust(left=0.20, right=0.93, top=0.90, bottom=0.02)
plt.savefig(f'{OUT}/fig_03_category_heatmap.pdf', bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_03_category_heatmap.pdf')
print(f"Done! fig_03_category_heatmap.pdf ({size // 1024} KB)")
