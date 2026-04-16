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

BLUE   = '#2563EB'
ORANGE = '#EA580C'

fig, ax = plt.subplots(figsize=(8, 4.5))

# Main effects: mean(ON) - mean(OFF)
main_effects_score = []
main_effects_mh    = []
for fi in range(4):
    on_mask  = factor_matrix[:, fi] == 1
    off_mask = factor_matrix[:, fi] == 0
    main_effects_score.append(scores[on_mask].mean() - scores[off_mask].mean())
    main_effects_mh.append(mh[on_mask].mean() - mh[off_mask].mean())

# SE via 8 paired contrasts: for factor fi, the other 3 factors define
# 8 unique combinations; each pair's contrast is (ON - OFF).
# SE = std(contrasts, ddof=1) / sqrt(8).
se_score = []
se_mh    = []
for fi in range(4):
    other = [j for j in range(4) if j != fi]
    diffs_s, diffs_m = [], []
    for combo_idx in range(8):
        combo    = [(combo_idx >> k) & 1 for k in range(3)]
        mask_on  = factor_matrix[:, fi] == 1
        mask_off = factor_matrix[:, fi] == 0
        for k, of in enumerate(other):
            mask_on  = mask_on  & (factor_matrix[:, of] == combo[k])
            mask_off = mask_off & (factor_matrix[:, of] == combo[k])
        if mask_on.sum() >= 1 and mask_off.sum() >= 1:
            diffs_s.append(float(scores[mask_on].mean()) - float(scores[mask_off].mean()))
            diffs_m.append(float(mh[mask_on].mean())     - float(mh[mask_off].mean()))
    arr_s = np.array(diffs_s)
    arr_m = np.array(diffs_m)
    se_score.append(np.std(arr_s, ddof=1) / np.sqrt(len(arr_s)))
    se_mh.append(np.std(arr_m, ddof=1) / np.sqrt(len(arr_m)))

y   = np.arange(4)
h   = 0.35
err_kw = dict(ecolor='#333333', capsize=3, elinewidth=1.2, capthick=1.2)

bars1 = ax.barh(y + h/2, main_effects_score, h,
                label='Score Effect (pp)', color=BLUE, edgecolor='white',
                xerr=se_score, error_kw=err_kw)
bars2 = ax.barh(y - h/2, main_effects_mh, h,
                label='Must-Have Effect (pp)', color=ORANGE, edgecolor='white',
                xerr=se_mh, error_kw=err_kw)

ax.set_yticks(y)
ax.set_yticklabels(FACTORS, fontsize=11)
ax.axvline(0, color='black', linewidth=0.8)
ax.set_xlabel('Effect (percentage points)', fontsize=11)
ax.legend(loc='lower right', fontsize=10)
ax.text(0.99, 0.01, '±1 SE (8 paired contrasts)',
        transform=ax.transAxes, ha='right', va='bottom',
        fontsize=8, color='#666666')

# Value labels — offset past the error bar cap
for i, bar in enumerate(bars1):
    w   = bar.get_width()
    pad = se_score[i] + 0.4
    ax.text(w + (pad if w >= 0 else -pad),
            bar.get_y() + bar.get_height() / 2,
            f'{w:+.1f}', va='center',
            ha='left' if w >= 0 else 'right',
            fontsize=9, fontweight='bold')
for i, bar in enumerate(bars2):
    w   = bar.get_width()
    pad = se_mh[i] + 0.4
    ax.text(w + (pad if w >= 0 else -pad),
            bar.get_y() + bar.get_height() / 2,
            f'{w:+.1f}', va='center',
            ha='left' if w >= 0 else 'right',
            fontsize=9, fontweight='bold')

plt.tight_layout()
plt.savefig(f'{OUT}/fig_01_main_effects.pdf', bbox_inches='tight')
plt.savefig(f'{OUT}/fig_01_main_effects.png', dpi=150, bbox_inches='tight')
plt.close()

size_pdf = os.path.getsize(f'{OUT}/fig_01_main_effects.pdf')
size_png = os.path.getsize(f'{OUT}/fig_01_main_effects.png')
print(f"Done! fig_01_main_effects.pdf ({size_pdf // 1024} KB), "
      f"fig_01_main_effects.png ({size_png // 1024} KB)")
