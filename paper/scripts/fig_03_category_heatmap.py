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
# v3 data: claude-opus-4-6, 5-judge panel (CHANINN_DEMO_DATA.APPS.V3_AEO_SCORES)
data = np.array([
    # R1 base
    [41.1, 66.5, 53.6, 50.1, 42.2, 51.9, 50.8, 68.9, 50.2, 46.6, 66.9, 59.6, 60.9, 53.0, 44.8, 47.8, 60.2, 63.1, 56.2, 29.4, 54.1, 47.8, 67.0, 51.5, 57.3, 35.4, 58.1, 47.1, 64.3, 55.6, 68.4, 43.3],
    # R2 D
    [40.6, 68.9, 55.4, 49.6, 44.6, 48.6, 52.9, 58.4, 49.5, 53.3, 63.8, 57.6, 53.0, 51.4, 40.8, 47.3, 59.4, 60.5, 55.6, 26.6, 52.1, 46.6, 64.3, 56.6, 58.6, 36.2, 60.5, 46.6, 64.3, 58.3, 61.1, 48.7],
    # R3 C
    [45.7, 67.0, 57.2, 51.3, 46.1, 49.4, 51.2, 61.2, 46.1, 50.7, 68.5, 55.9, 59.7, 55.4, 47.5, 46.0, 61.0, 57.6, 58.2, 25.4, 56.0, 44.1, 63.8, 51.6, 57.5, 39.4, 62.1, 43.0, 66.1, 62.6, 65.9, 45.0],
    # R4 DC
    [41.4, 67.4, 53.5, 45.8, 41.5, 53.7, 48.8, 53.8, 48.7, 51.4, 62.4, 56.5, 59.2, 58.5, 43.8, 43.5, 60.2, 59.4, 55.8, 27.2, 53.1, 45.7, 61.9, 52.7, 58.5, 36.4, 58.6, 49.9, 65.8, 57.1, 66.7, 47.8],
    # R5 A
    [50.6, 65.8, 50.1, 52.1, 60.5, 52.0, 70.5, 70.8, 66.7, 57.6, 62.7, 64.1, 68.4, 60.9, 56.8, 57.5, 73.5, 59.7, 60.3, 55.9, 67.0, 53.9, 72.7, 64.3, 60.1, 59.3, 72.6, 61.5, 71.8, 68.0, 67.3, 67.0],
    # R6 DA
    [45.2, 70.1, 56.3, 49.5, 59.8, 52.4, 65.4, 70.4, 63.3, 58.7, 63.9, 66.1, 65.9, 57.7, 55.2, 63.1, 72.0, 65.2, 60.4, 51.6, 71.3, 57.8, 69.5, 67.8, 59.5, 54.2, 70.5, 63.8, 71.2, 69.0, 71.6, 66.3],
    # R7 CA (best)
    [59.6, 65.2, 63.4, 58.4, 65.5, 55.5, 78.5, 75.2, 68.2, 64.0, 76.2, 70.8, 69.4, 69.8, 56.0, 74.7, 77.1, 73.2, 68.5, 65.2, 70.8, 59.3, 70.1, 77.3, 67.2, 60.4, 77.2, 70.5, 83.9, 79.7, 72.3, 72.5],
    # R8 DCA
    [56.2, 73.2, 72.2, 53.2, 64.5, 63.4, 73.7, 73.5, 66.3, 64.1, 71.6, 67.9, 68.3, 61.1, 62.2, 56.4, 69.9, 65.4, 69.2, 58.9, 75.9, 60.4, 73.5, 76.5, 67.2, 59.8, 72.4, 67.7, 75.5, 73.5, 79.6, 64.7],
    # R9 S
    [45.9, 68.4, 58.5, 46.9, 45.1, 52.2, 49.1, 55.2, 47.7, 44.6, 60.7, 53.4, 57.9, 55.7, 40.6, 46.7, 59.8, 61.7, 58.2, 28.3, 52.6, 46.1, 63.9, 52.3, 56.4, 32.3, 57.1, 44.3, 60.7, 56.4, 67.9, 47.3],
    # R10 DS
    [46.2, 68.3, 56.4, 47.7, 40.8, 49.3, 45.1, 60.7, 47.1, 51.5, 66.3, 55.5, 57.9, 51.9, 48.0, 41.2, 60.6, 60.1, 57.7, 28.8, 51.2, 46.6, 66.6, 52.8, 57.4, 32.3, 59.9, 43.4, 64.0, 59.0, 64.4, 49.7],
    # R11 CS
    [38.7, 68.9, 55.9, 48.0, 41.0, 49.8, 46.8, 61.3, 48.2, 44.8, 65.3, 56.2, 54.9, 55.5, 36.0, 47.2, 58.6, 57.0, 55.6, 29.3, 57.1, 47.2, 65.7, 57.4, 57.5, 35.4, 58.7, 48.8, 64.9, 61.4, 64.0, 45.2],
    # R12 DCS
    [42.9, 65.6, 54.0, 49.9, 48.4, 52.8, 50.0, 70.4, 48.1, 54.9, 65.8, 58.6, 49.9, 55.2, 47.5, 43.5, 58.3, 62.5, 54.3, 25.6, 55.1, 52.3, 69.2, 54.0, 59.1, 36.7, 58.4, 45.7, 65.0, 61.7, 62.8, 48.4],
    # R13 AS
    [37.4, 64.3, 45.4, 42.1, 50.3, 47.6, 65.4, 66.8, 54.3, 56.9, 65.0, 57.4, 62.2, 65.5, 50.2, 57.8, 64.6, 56.2, 56.1, 48.2, 63.7, 46.8, 69.8, 58.8, 60.1, 44.2, 63.5, 61.9, 69.1, 61.9, 65.5, 61.5],
    # R14 DAS
    [40.2, 64.9, 58.9, 48.2, 51.1, 48.4, 53.0, 67.7, 59.0, 57.9, 56.4, 55.3, 60.5, 58.3, 56.1, 60.5, 59.6, 58.2, 57.6, 56.2, 62.7, 54.3, 67.1, 60.8, 61.0, 57.3, 54.5, 60.2, 65.1, 64.8, 68.9, 55.1],
    # R15 CAS
    [39.5, 56.1, 66.4, 38.7, 53.4, 49.4, 62.0, 67.3, 58.0, 58.0, 60.1, 52.3, 61.2, 56.6, 52.7, 60.2, 59.8, 50.9, 52.8, 53.2, 66.8, 53.3, 65.0, 63.2, 57.0, 45.2, 67.5, 59.5, 65.9, 65.5, 60.0, 59.5],
    # R16 DCAS
    [34.3, 61.9, 56.7, 39.3, 56.6, 43.6, 59.4, 67.0, 53.1, 55.1, 51.6, 54.9, 58.7, 60.5, 53.7, 63.6, 61.6, 62.0, 55.6, 47.9, 64.7, 41.4, 61.2, 56.2, 63.1, 59.4, 70.5, 65.7, 64.0, 67.9, 71.2, 57.0],
])

# Overall run scores (Yates order)
overall_scores = [53.6, 52.9, 53.7, 52.7, 62.6, 62.6, 69.2, 67.4,
                  52.3, 52.8, 52.6, 54.0, 57.5, 58.1, 57.4, 57.5]

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
