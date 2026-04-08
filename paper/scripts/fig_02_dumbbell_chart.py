"""
AEO Figure 2: Dumbbell Chart
Baseline (R1) vs Best Configuration (R4) by product category.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.facecolor': 'white',
})

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

RED = '#DC2626'
GREEN = '#16A34A'

categories = [
    ('Native Apps Framework',       43.3, 98.4),
    ('Snowpark',                    49.3, 99.3),
    ('Cortex AI Functions',         41.3, 91.3),
    ('Architecture & Fundamentals', 54.4, 97.8),
    ('Snowflake ML',                51.3, 90.0),
    ('SPCS',                        67.5, 100.0),
    ('Apache Iceberg Tables',       67.4, 96.7),
    ('Dynamic Tables',              69.3, 96.7),
    ('Cortex Search (RAG)',         70.0, 94.1),
    ('Streams, Tasks, Snowpipe',    75.6, 100.0),
    ('Governance & Security',       73.4, 96.6),
    ('Cortex Agents',               57.7, 68.9),
    ('Streamlit in Snowflake',      76.6, 88.3),
]

# Sort by delta descending
categories.sort(key=lambda x: x[2] - x[1], reverse=True)

fig, ax = plt.subplots(figsize=(10, 7))

for i, (cat, base, best) in enumerate(categories):
    y = len(categories) - 1 - i
    delta = best - base
    ax.plot([base, best], [y, y], color='#D1D5DB', linewidth=6, solid_capstyle='round', zorder=1)
    ax.scatter(base, y, s=80, color=RED, zorder=2, label='Baseline (R1)' if i == 0 else '')
    ax.scatter(best, y, s=80, color=GREEN, zorder=2, label='Best (R4)' if i == 0 else '')
    ax.text(best + 1.2, y, f'+{delta:.1f}pp', va='center', fontsize=9, color=GREEN, fontweight='bold')

ax.set_yticks(range(len(categories)))
ax.set_yticklabels([c[0] for c in reversed(categories)], fontsize=10)
ax.set_xlabel('Score %', fontsize=11)
ax.set_xlim(35, 110)
ax.set_title('Category Improvement: Baseline vs Best Configuration', fontsize=14, fontweight='bold', pad=15)
ax.legend(loc='lower right', fontsize=10)
ax.axvline(50, color='#E5E7EB', linewidth=0.5, zorder=0)
ax.axvline(75, color='#E5E7EB', linewidth=0.5, zorder=0)
ax.axvline(100, color='#E5E7EB', linewidth=0.5, zorder=0)

plt.tight_layout()
plt.savefig(f'{OUT}/fig_02_dumbbell_chart.png', dpi=200, bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_02_dumbbell_chart.png')
print(f"Done! fig_02_dumbbell_chart.png ({size // 1024} KB)")
