"""
AEO Figure 1: Main Effects Bar Chart
Shows the average impact of each factor on Score and Must-Have compliance.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# 16 runs: (Run#, Domain, Citation, Agentic, SC, Score%, MH%)
RUNS = [
    (1,  0, 0, 0, 0, 60.9, 68.5),
    (2,  1, 0, 0, 0, 71.5, 63.5),
    (3,  0, 0, 1, 0, 72.2, 93.5),
    (4,  0, 1, 1, 0, 93.8, 91.5),
    (5,  1, 1, 0, 0, 71.5, 54.5),
    (6,  0, 1, 0, 0, 71.1, 48.5),
    (7,  0, 1, 1, 1, 93.2, 93.5),
    (8,  1, 1, 1, 1, 73.0, 91.2),
    (9,  1, 0, 1, 0, 70.4, 89.8),
    (10, 1, 1, 1, 0, 76.0, 90.5),
    (11, 0, 0, 0, 1, 56.9, 66.5),
    (12, 1, 0, 0, 1, 62.0, 69.0),
    (13, 0, 1, 0, 1, 65.7, 60.7),
    (14, 1, 1, 0, 1, 67.4, 69.3),
    (15, 0, 0, 1, 1, 70.8, 88.2),
    (16, 1, 0, 1, 1, 71.2, 88.7),
]

FACTORS = ['Domain', 'Citation', 'Agentic', 'Self-Critique']

runs = np.array(RUNS)
factor_matrix = runs[:, 1:5].astype(int)
scores = runs[:, 5]
mh = runs[:, 6]

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.facecolor': 'white',
})

BLUE = '#2563EB'
ORANGE = '#EA580C'

fig, ax = plt.subplots(figsize=(8, 4.5))

main_effects_score = []
main_effects_mh = []
for fi in range(4):
    on_mask = factor_matrix[:, fi] == 1
    off_mask = factor_matrix[:, fi] == 0
    main_effects_score.append(scores[on_mask].mean() - scores[off_mask].mean())
    main_effects_mh.append(mh[on_mask].mean() - mh[off_mask].mean())

y = np.arange(4)
h = 0.35
bars1 = ax.barh(y + h/2, main_effects_score, h, label='Score Effect (pp)', color=BLUE, edgecolor='white')
bars2 = ax.barh(y - h/2, main_effects_mh, h, label='Must-Have Effect (pp)', color=ORANGE, edgecolor='white')

ax.set_yticks(y)
ax.set_yticklabels(FACTORS, fontsize=12)
ax.axvline(0, color='black', linewidth=0.8)
ax.set_xlabel('Effect (percentage points)', fontsize=11)
ax.set_title('Main Effects of Each Factor on Answer Quality', fontsize=14, fontweight='bold', pad=15)
ax.legend(loc='lower right', fontsize=10)

for bar in bars1:
    w = bar.get_width()
    ax.text(w + (0.5 if w >= 0 else -0.5), bar.get_y() + bar.get_height()/2,
            f'{w:+.1f}', va='center', ha='left' if w >= 0 else 'right', fontsize=9, fontweight='bold')
for bar in bars2:
    w = bar.get_width()
    ax.text(w + (0.5 if w >= 0 else -0.5), bar.get_y() + bar.get_height()/2,
            f'{w:+.1f}', va='center', ha='left' if w >= 0 else 'right', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig(f'{OUT}/fig_01_main_effects.png', dpi=200, bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_01_main_effects.png')
print(f"Done! fig_01_main_effects.png ({size // 1024} KB)")
