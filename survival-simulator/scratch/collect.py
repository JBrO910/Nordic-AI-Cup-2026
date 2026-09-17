"""Summarise detached per-seed runs: python scratch/collect.py <tag> [<tag> ...]  (reads scratch/res_<tag>_<seed>.txt)"""
import glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
for tag in sys.argv[1:]:
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, f"res_{tag}_*.txt"))):
        for line in open(f, encoding="utf-8", errors="ignore"):
            m = re.match(r"seed\s+(\d+) \| score\s+([\d.]+) \| survived\s+([\d.]+)s .*?kills\s+(\d+) \(-([\d.]+)\)", line)
            if m:
                rows.append(tuple(float(x) for x in m.groups()))
    if not rows:
        print(f"{tag}: no results"); continue
    n = len(rows)
    print(f"{tag}: n={n} | mean score {sum(r[1] for r in rows)/n:.1f} | mean survived {sum(r[2] for r in rows)/n:.1f}s "
          f"| min survived {min(r[2] for r in rows):.1f}s | kills/run {sum(r[3] for r in rows)/n:.1f} | "
          f"per-seed survived: {' '.join(f'{int(r[0])}:{r[2]:.0f}' for r in rows)}")
