# -*- coding: utf-8 -*-
"""用修正后的评分器重新评分所有 results/*.jsonl 中的探针回答, 覆盖式生成 rescored 汇总。
用法: python rescore.py"""
import json, glob, os, sys, importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tb", os.path.join(ROOT, "..", "tests", "testbed.py"))
tb = importlib.util.module_from_spec(spec)
import argparse
sys.argv = ["x", "--model", "x", "--mode", "psm"]  # 防止 argparse 误吃
# 手动执行模块主体但不跑 main: 直接exec_module会触发 __main__ 保护? 模块名非__main__, 安全
spec.loader.exec_module(tb)

def rescore_file(path):
    tb.FACTS_USE, tb.TRAPS_USE = (tb.FACTS, tb.TRAPS) if "_v2" not in os.path.basename(path) else (tb.FACTS_V2, tb.TRAPS_V2)
    probes = []
    summary = None
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        if "summary" in d:
            summary = d["summary"]
            continue
        for p in d.get("probes", []):
            s = tb.score_probe(p["probe_id"], p.get("answer") or "")
            s.update({"probe_id": p["probe_id"], "after_turn": p["after_turn"], "question": p["question"]})
            if p["score"] != s["score"] or p.get("hallucination") != s.get("hallucination"):
                s["changed"] = True
            probes.append(s)
    if summary is None or not probes:
        return None
    rec = [p for p in probes if not p["probe_id"].startswith("TRAP")]
    trp = [p for p in probes if p["probe_id"].startswith("TRAP")]
    return {
        "model": summary["model"], "mode": summary["mode"], "script": summary.get("script", "v1"),
        "recall_acc": round(sum(p["score"] for p in rec) / max(1, len(rec)), 3),
        "trap_halluc_rate": round(sum(1 for p in trp if p["hallucination"]) / max(1, len(trp)), 3),
        "n_probes": len(probes), "n_changed": sum(1 for p in probes if p.get("changed")),
        "file": os.path.basename(path),
    }

rows = []
for f in sorted(glob.glob(os.path.join(ROOT, "*.jsonl")), key=os.path.getmtime):
    r = rescore_file(f)
    if r:
        rows.append(r)
out = os.path.join(ROOT, "rescored_summary.json")
json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{'model':<14}{'mode':<10}{'script':<8}{'recall':<8}{'halluc':<8}{'n':<4}{'chg':<4}file")
for r in rows:
    print(f"{r['model']:<14}{r['mode']:<10}{r['script']:<8}{r['recall_acc']:<8}{r['trap_halluc_rate']:<8}{r['n_probes']:<4}{r['n_changed']:<4}{r['file']}")
