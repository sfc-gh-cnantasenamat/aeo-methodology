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

# (category, baseline %, best C+A %)
# v3 data: claude-opus-4-6, base vs CA, 5-judge panel (CHANINN_DEMO_DATA.APPS.V3_AEO_SCORES)
categories = [
    ('AI Observability & Evaluation',       41.1, 59.6),
    ('Apache Iceberg Tables',               66.5, 65.2),
    ('Collaboration & Data Sharing',        53.6, 63.4),
    ('Cortex AI Function Studio',           50.1, 58.4),
    ('Cortex AI Functions',                 42.2, 65.5),
    ('Cortex Agents',                       51.9, 55.5),
    ('Cortex Code',                         50.8, 78.5),
    ('Cortex Search',                       68.9, 75.2),
    ('Cost Management',                     50.2, 68.2),
    ('Data Clean Rooms',                    46.6, 64.0),
    ('Data Governance & Security',          66.9, 76.2),
    ('Data Loading (COPY/Snowpipe)',        59.6, 70.8),
    ('Data Pipelines (Streams/Tasks)',      60.9, 69.4),
    ('Data Quality & Observability',        53.0, 69.8),
    ('Database Change Management (DCM)',    44.8, 56.0),
    ('Database Security',                   47.8, 74.7),
    ('Dynamic Tables',                      60.2, 77.1),
    ('Hybrid Tables',                       63.1, 73.2),
    ('Native Apps Framework',               56.2, 68.5),
    ('Openflow',                            29.4, 65.2),
    ('SQL Performance & Optimization',      54.1, 70.8),
    ('Semantic Views & Cortex Analyst',     47.8, 59.3),
    ('Snowflake Fundamentals & Arch.',      67.0, 70.1),
    ('Snowflake ML',                        51.5, 77.3),
    ('Snowflake Notebooks',                 57.3, 67.2),
    ('Snowflake Postgres',                  35.4, 60.4),
    ('Snowpark',                            58.1, 77.2),
    ('Snowpark Connect & Migration',        47.1, 70.5),
    ('Snowpark Container Services',         64.3, 83.9),
    ('Snowsight',                           55.6, 79.7),
    ('Streamlit in Snowflake',              68.4, 72.3),
    ('dbt Projects on Snowflake',           43.3, 72.5),
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
