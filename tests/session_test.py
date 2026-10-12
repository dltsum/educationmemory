# -*- coding: utf-8 -*-
"""
v3 跨会话测试: 模拟"隔天再来"场景
  会话A: 12轮事实披露 (SCRIPT[:12])
  ---- 跨夜: linear 只能携带全部转录; psm 只携带学生卡片 ----
  会话B: 探针测验 (6题: 4回忆 + 2陷阱)
对比: 回忆准确率 / 幻觉率 / 每轮上下文字符数(成本代理)
用法: python session_test.py --model mimo-v2.5 --mode linear|psm
"""
import argparse, json, os, datetime, importlib.util, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tb", os.path.join(ROOT, "testbed.py"))
tb = importlib.util.module_from_spec(spec)  # testbed 的 argparse 在 __main__ 保护下, 导入安全
spec.loader.exec_module(tb)

SESSION_B_PROBES = [
    ("name", None), ("weak_kc", None), ("style", None), ("exam_date", None),
    ("TRAP0", None), ("TRAP1", None),
]

def run(model, mode):
    tag = datetime.datetime.now().strftime("%m%d_%H%M%S")
    out = os.path.join(ROOT, "..", "results", f"v3_{model}_{mode}_{tag}.jsonl")
    log = open(out, "w", encoding="utf-8")
    history, state = [], json.loads(json.dumps(tb.EMPTY_STATE))
    ctx_lens, probe_results = [], []

    def build(user_msg):
        if mode == "linear":
            return [{"role": "system", "content": tb.SYSTEM_TUTOR}] + history + [{"role": "user", "content": user_msg}]
        card = tb.compile_card(state)
        return [{"role": "system", "content": tb.SYSTEM_TUTOR + "\n\n" + card}] + history[-4:] + [{"role": "user", "content": user_msg}]

    def step(student):
        msgs = build(student)
        ctx_lens.append(sum(len(m["content"]) for m in msgs))
        ans = tb.call_llm(model, msgs) or "(API失败)"
        history.extend([{"role": "user", "content": student}, {"role": "assistant", "content": ans}])
        if mode == "psm":
            ext = tb.call_llm(model, [{"role": "user", "content": tb.EXTRACT_PROMPT.format(
                state=json.dumps(state, ensure_ascii=False)[:1500], student=student, tutor=ans[:500])}], max_tokens=4000)
            upd = tb.parse_json_loose(ext)
            if upd:
                tb.apply_updates(state, upd)
        return ans

    # 会话 A
    for turn, student in tb.SCRIPT[:12]:
        ans = step(student)
        log.write(json.dumps({"session": "A", "turn": turn, "student": student, "answer": ans}, ensure_ascii=False) + "\n")
        log.flush()
        print(f"[v3|{model}|{mode}] A{turn} done", flush=True)

    # ---- 跨夜: linear 携带全部转录; psm 丢弃原文只留卡片 ----
    if mode == "psm":
        history = []  # 新会话, 原文不可得, 只有结构化状态
        log.write(json.dumps({"event": "session_break", "kept": "card_only"}) + "\n")
    else:
        log.write(json.dumps({"event": "session_break", "kept": "full_transcript",
                              "transcript_chars": sum(len(m["content"]) for m in history)}) + "\n")

    # 会话 B: 探针
    for pid, _ in SESSION_B_PROBES:
        q = tb.TRAPS[int(pid[-1])]["probe"] if pid.startswith("TRAP") else tb.FACTS[pid]["probe"]
        msgs = build(q)
        ctx_lens.append(sum(len(m["content"]) for m in msgs))
        ans = tb.call_llm(model, msgs) or ""
        s = tb.score_probe(pid, ans)
        s.update({"probe_id": pid, "question": q, "answer": ans})
        probe_results.append(s)
        history.extend([{"role": "user", "content": q}, {"role": "assistant", "content": ans}])
        log.write(json.dumps({"session": "B", "probe": s}, ensure_ascii=False) + "\n")
        log.flush()
        print(f"[v3|{model}|{mode}] B probe {pid} score={s['score']}", flush=True)

    rec = [p for p in probe_results if not p["probe_id"].startswith("TRAP")]
    trp = [p for p in probe_results if p["probe_id"].startswith("TRAP")]
    summary = {"model": model, "mode": mode, "script": "v3",
               "recall_acc": round(sum(p["score"] for p in rec) / max(1, len(rec)), 3),
               "trap_halluc_rate": round(sum(1 for p in trp if p["hallucination"]) / max(1, len(trp)), 3),
               "avg_ctx_chars": round(sum(ctx_lens) / len(ctx_lens)),
               "max_ctx_chars": max(ctx_lens),
               "n_probes": len(probe_results)}
    log.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
    log.close()
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["linear", "psm"], required=True)
    a = ap.parse_args()
    run(a.model, a.mode)
