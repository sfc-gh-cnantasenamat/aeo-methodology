"""
AEO Figure 1: Main Effects Bar Chart
Shows the average impact of each factor on Score and Must-Have compliance.
128-question / 32-category dataset.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')

# 16 runs: (Run#, Domain, Citation, Agentic, SC, Score%, MH%)
# Yates order: D=bit0, C=bit1, A=bit2, SC=bit3
RUNS = [
    (1,  0, 0, 0, 0, 53.2, 62.7),
    (2,  1, 0, 0, 0, 57.8, 66.1),
    (3,  0, 1, 0, 0, 67.7, 62.4),
    (4,  1, 1, 0, 0, 66.1, 64.8),
    (5,  0, 0, 1, 0, 74.4, 96.3),
    (6,  1, 0, 1, 0, 69.4, 86.0),
    (7,  0, 1, 1, 0, 82.3, 87.7),
    (8,  1, 1, 1, 0, 76.0, 82.7),
    (9,  0, 0, 0, 1, 56.1, 60.5),
    (10, 1, 0, 0, 1, 58.4, 63.6),
    (11, 0, 1, 0, 1, 67.2, 55.0),
    (12, 1, 1, 0, 1, 66.1, 57.8),
    (13, 0, 0, 1, 1, 66.1, 76.6),
    (14, 1, 0, 1, 1, 65.4, 76.3),
    (15, 0, 1, 1, 1, 72.4, 69.0),
    (16, 1, 1, 1, 1, 73.5, 71.8),
]

FACTORS = ['Domain\nPrompt', 'Citation\nInstruction', 'Agentic\nTools', 'Self-\nCritique']

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
ax.set_yticklabels(FACTORS, fontsize=11)
ax.axvline(0, color='black', linewidth=0.8)
ax.set_xlabel('Effect (percentage points)', fontsize=11)
ax.legend(loc='lower right', fontsize=10)

for bar in bars1:
    w = bar.get_width()
    ax.text(w + (0.3 if w >= 0 else -0.3), bar.get_y() + bar.get_height()/2,
            f'{w:+.1f}', va='center', ha='left' if w >= 0 else 'right', fontsize=9, fontweight='bold')
for bar in bars2:
    w = bar.get_width()
    ax.text(w + (0.3 if w >= 0 else -0.3), bar.get_y() + bar.get_height()/2,
            f'{w:+.1f}', va='center', ha='left' if w >= 0 else 'right', fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig(f'{OUT}/fig_01_main_effects.pdf', bbox_inches='tight')
plt.close()

size = os.path.getsize(f'{OUT}/fig_01_main_effects.pdf')
print(f"Done! fig_01_main_effects.pdf ({size // 1024} KB)")
