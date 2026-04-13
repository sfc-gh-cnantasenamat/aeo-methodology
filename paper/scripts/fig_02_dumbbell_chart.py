"""
AEO Figure 2: Dumbbell Chart
Baseline (Run 1, all OFF) vs Best Configuration (Run 7, C+A) by product category.
128-question / 32-category dataset.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 10,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.facecolor': 'white',
})

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

RED = '#DC2626'
GREEN = '#16A34A'

# (category, baseline Run 1 %, best Run 7 %)
categories = [
    ('Data Governance & Security',          66.2, 90.8),
    ('dbt Projects on Snowflake',           42.2, 90.3),
    ('Cortex Code',                         49.8, 88.8),
    ('Apache Iceberg Tables',               69.3, 88.3),
    ('Cortex Search',                       59.3, 88.3),
    ('Cost Management',                     51.0, 87.5),
    ('Snowflake Fundamentals & Arch.',      62.2, 87.5),
    ('Collaboration & Data Sharing',        55.3, 86.8),
    ('Streamlit in Snowflake',              61.3, 86.3),
    ('Snowpark',                            61.5, 86.2),
    ('Snowpark Container Services',         66.0, 85.3),
    ('Cortex AI Function Studio',           54.7, 84.7),
    ('Snowflake ML',                        53.7, 84.3),
    ('Database Security',                   43.0, 84.2),
    ('Openflow',                            26.7, 83.2),
    ('Cortex AI Functions',                 43.7, 83.0),
    ('Native Apps Framework',               47.8, 82.8),
    ('Hybrid Tables',                       59.5, 82.8),
    ('SQL Performance & Optimization',      59.5, 82.7),
    ('Data Pipelines (Streams/Tasks)',       54.5, 81.5),
    ('Snowpark Connect & Migration',        51.3, 81.2),
    ('Snowflake Notebooks',                 58.3, 80.8),
    ('AI Observability & Evaluation',       46.3, 80.2),
    ('Data Clean Rooms',                    46.5, 79.3),
    ('Semantic Views & Cortex Analyst',     48.8, 79.2),
    ('Cortex Agents',                       49.5, 78.5),
    ('Database Change Management (DCM)',    46.2, 78.0),
    ('Data Loading (COPY/Snowpipe)',        55.6, 77.2),
    ('Snowsight',                           61.2, 76.8),
    ('Dynamic Tables',                      57.7, 75.0),
    ('Data Quality & Observability',        54.3, 69.2),
    ('Snowflake Postgres',                  38.0, 61.8),
]

# Sort by delta descending
categories.sort(key=lambda x: x[2] - x[1], reverse=True)

fig, ax = plt.subplots(figsize=(10, 13))

for i, (cat, base, best) in enumerate(categories):
    y = len(categories) - 1 - i
    delta = best - base
    ax.plot([base, best], [y, y], color='#D1D5DB', linewidth=5, solid_capstyle='round', zorder=1)
    ax.scatter(base, y, s=60, color=RED, zorder=2, label='Baseline (R1)' if i == 0 else '')
    ax.scatter(best, y, s=60, color=GREEN, zorder=2, label='Best: C+A (R7)' if i == 0 else '')
    ax.text(best + 1.0, y, f'+{delta:.1f}pp', va='center', fontsize=8, color=GREEN, fontweight='bold')

ax.set_yticks(range(len(categories)))
ax.set_yticklabels([c[0] for c in reversed(categories)], fontsize=9)
ax.set_xlabel('Score %', fontsize=11)
ax.set_xlim(20, 105)
ax.legend(loc='lower right', fontsize=10)
for v in [40, 60, 80, 100]:
    ax.axvline(v, color='#E5E7EB', linewidth=0.5, zorder=0)

plt.tight_layout()
plt.savefig(f'{OUT}/fig_02_dumbbell_chart.pdf', bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_02_dumbbell_chart.pdf')
print(f"Done! fig_02_dumbbell_chart.pdf ({size // 1024} KB)")
