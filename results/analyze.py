# -*- coding: utf-8 -*-
"""聚合 results/*.jsonl 的 summary, 输出对比表。"""
import json, glob, os, sys

def main():
    rows = {}
    for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "*.jsonl")), key=os.path.getmtime):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            if "summary" in d:
                s = d["summary"]
                rows[(s["model"], s["mode"], os.path.basename(f))] = s
    print(f"{'model':<14}{'mode':<10}{'recall_acc':<12}{'trap_halluc':<12}{'n_probes':<9}file")
    for (m, mode, f), s in rows.items():
        print(f"{m:<14}{mode:<10}{s['recall_acc']:<12}{s['trap_halluc_rate']:<12}{s['n_probes']:<9}{f}")
    if "--detail" in sys.argv:
        for (m, mode, f), s in rows.items():
            if s.get("final_state"):
                print(f"\n== {m}/{mode} final_state ==")
                print(json.dumps(s["final_state"], ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
