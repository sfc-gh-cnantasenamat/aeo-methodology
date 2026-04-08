"""
AEO 2^4 Factorial Heatmap
16 runs (rows) x 13 categories (columns), cells colored by score %.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# Categories and their scores per run (R1-R16 in run order)
categories = [
    'Cortex AI\nFunctions',
    'Cortex\nSearch',
    'Cortex\nAgents',
    'Dynamic\nTables',
    'Snowpark',
    'Streamlit\nin Snowflake',
    'Iceberg\nTables',
    'Snowflake\nML',
    'SPCS',
    'Native\nApps',
    'Streams\nTasks',
    'Governance\nSecurity',
    'Architecture\nFundamentals',
]

# Score % by category, rows = R1..R16 in run order
data = np.array([
    [41.3, 70.0, 57.7, 69.3, 49.3, 76.6, 67.4, 51.3, 67.5, 43.3, 75.6, 73.4, 54.4],  # R1
    [80.7, 80.0, 71.1, 91.3, 58.0, 74.2, 63.4, 83.3, 63.3, 50.0, 68.9, 78.3, 48.8],  # R2
    [66.0, 71.7, 56.7, 79.4, 74.7, 70.9, 72.1, 70.7, 76.7, 66.7, 78.9, 73.4, 76.7],  # R3
    [91.3, 94.1, 68.9, 96.7, 99.3, 88.3, 96.7, 90.0, 100., 98.4, 100., 96.6, 97.8],  # R4
    [64.6, 82.5, 68.9, 84.0, 61.3, 75.0, 62.0, 74.6, 70.9, 63.3, 90.0, 80.0, 54.4],  # R5
    [67.3, 87.5, 73.3, 67.4, 56.7, 65.0, 70.0, 76.7, 86.7, 73.3, 82.2, 56.7, 61.1],  # R6
    [86.0, 90.1, 75.6, 94.7, 95.4, 96.7, 95.4, 91.4, 98.4, 98.4, 100., 98.4, 95.6],  # R7
    [72.7, 76.6, 41.1, 73.3, 76.0, 79.2, 72.0, 68.0, 79.2, 75.0, 78.9, 76.6, 78.9],  # R8
    [67.3, 71.7, 44.5, 77.3, 78.0, 72.5, 65.3, 60.0, 75.0, 76.6, 78.9, 71.7, 78.9],  # R9
    [78.6, 82.5, 52.2, 74.7, 79.3, 81.7, 69.3, 66.0, 74.2, 80.0, 96.7, 85.0, 76.7],  # R10
    [42.0, 62.5, 47.2, 62.0, 58.7, 57.9, 55.3, 46.0, 68.3, 55.0, 70.0, 61.7, 62.2],  # R11
    [60.0, 72.5, 57.8, 63.3, 61.7, 73.3, 58.0, 44.0, 68.3, 70.0, 64.4, 68.3, 54.5],  # R12
    [43.3, 70.0, 48.9, 74.3, 76.7, 72.5, 66.7, 58.7, 69.2, 68.3, 60.0, 82.5, 71.1],  # R13
    [60.7, 66.7, 64.4, 69.0, 76.3, 61.6, 53.3, 62.0, 76.2, 86.7, 77.8, 71.7, 66.7],  # R14
    [70.0, 70.0, 54.4, 75.3, 75.3, 78.4, 65.7, 63.3, 70.0, 75.0, 81.1, 66.7, 76.7],  # R15
    [70.0, 72.5, 47.8, 74.7, 76.0, 75.0, 67.0, 66.7, 74.2, 63.3, 81.1, 75.0, 78.9],  # R16
])

# Overall scores for sorting
overall_scores = [60.9, 71.5, 72.2, 93.8, 71.5, 71.1, 93.2, 73.0, 70.4, 76.0,
                  56.9, 62.0, 65.7, 67.4, 70.8, 71.2]

# Run labels with factor annotations
# D=Domain, C=Citation, A=Agentic, S=Self-Critique
run_configs = [
    'Baseline (R1)',
    'D (R2)',
    'A (R3)',
    'C + A (R4)',
    'D + C (R5)',
    'C (R6)',
    'C + A + S (R7)',
    'D + C + A + S (R8)',
    'D + A (R9)',
    'D + C + A (R10)',
    'S (R11)',
    'D + S (R12)',
    'C + S (R13)',
    'D + C + S (R14)',
    'A + S (R15)',
    'D + A + S (R16)',
]

# Sort: Agentic runs first (upper half), then non-Agentic (lower half)
# Within each group, sort by score descending
agentic_flags = [0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1]  # R1-R16
# Create sort key: (-agentic, -score) so agentic=1 comes first, then highest score first
sort_key = [(-agentic_flags[i], -overall_scores[i]) for i in range(16)]
sort_idx = sorted(range(16), key=lambda i: sort_key[i])
sorted_data = data[sort_idx]
sorted_labels = [run_configs[i] for i in sort_idx]
sorted_scores = [overall_scores[i] for i in sort_idx]
sorted_agentic = [agentic_flags[i] for i in sort_idx]

# Find boundary between agentic and non-agentic
n_agentic = sum(agentic_flags)

# Append Average column
avg_col = np.array(sorted_scores).reshape(-1, 1)
plot_data = np.hstack([sorted_data, avg_col])
col_labels = categories + ['Average']

fig, ax = plt.subplots(figsize=(15, 9))

cmap = plt.cm.RdYlGn
im = ax.imshow(plot_data, cmap=cmap, aspect='auto', vmin=40, vmax=100)

# Add text annotations
nrows, ncols = plot_data.shape
for i in range(nrows):
    for j in range(ncols):
        val = plot_data[i, j]
        # Dark text on light cells, light text on dark cells
        text_color = 'white' if val < 55 or val > 92 else 'black'
        fontsize = 10.5 if j == ncols - 1 else 9.5  # Slightly larger for Average
        ax.text(j, i, f'{val:.1f}' if j == ncols - 1 else f'{val:.0f}',
                ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=text_color)

# Vertical separator line before Average column
ax.axvline(ncols - 1.5, color='black', linewidth=2)

# Horizontal separator between Agentic (upper) and non-Agentic (lower) groups
ax.axhline(n_agentic - 0.5, color='black', linewidth=2.5)

# Row labels (config only, no bracket score)
ax.set_yticks(range(16))
ax.set_yticklabels(sorted_labels, fontsize=9, fontfamily='monospace')

# Group labels on right side (between heatmap and colorbar)
ax.text(ncols - 0.15, (n_agentic - 1) / 2, 'Agentic',
        ha='center', va='center', fontsize=13, fontweight='bold',
        rotation=-90, color='#2166ac')
ax.text(ncols - 0.15, n_agentic + (16 - n_agentic - 1) / 2, 'Non-Agentic',
        ha='center', va='center', fontsize=13, fontweight='bold',
        rotation=-90, color='#b2182b')

# Column labels
ax.set_xticks(range(ncols))
ax.set_xticklabels(col_labels, fontsize=8, ha='center')
ax.tick_params(axis='x', top=True, bottom=False, labeltop=True, labelbottom=False)

# Colorbar (positioned to the right of Agentic/Non-Agentic labels)
cbar = plt.colorbar(im, ax=ax, shrink=0.7, pad=0.08)
cbar.set_label('Score %', fontsize=11)

ax.set_title('2^4 Factorial Heatmap: Score % by Run and Product Category',
             fontsize=14, fontweight='bold', pad=60)

# Grid lines
for i in range(17):
    ax.axhline(i - 0.5, color='white', linewidth=0.5)
for j in range(15):
    if j != ncols - 1:  # skip where the black separator is
        ax.axvline(j - 0.5, color='white', linewidth=0.5)

plt.tight_layout()
plt.savefig(f'{OUT}/fig_03_category_heatmap.png', dpi=200, bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_03_category_heatmap.png')
print(f"Done! fig_03_category_heatmap.png ({size // 1024} KB)")
