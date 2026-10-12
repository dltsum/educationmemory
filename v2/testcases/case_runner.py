# -*- coding: utf-8 -*-
"""
测试用例集执行器: 用 student_cases.json 驱动 v2 三层记忆流水线
流程/用例: 档案注入 → MathDial 对话重放 → 整理 → 压缩 → 8探针×3策略
探针4类: recall(档案直查) / graph_reason(图谱推理) / stats_reason(频次推理) / trap(幻觉陷阱)
评分: expect 关键词命中; trap 需回避词(明说不知道)=正确, 编造=幻觉
用法: python case_runner.py --model mimo-v2.5 [--cases 5] [--no-dialogue]
"""
import argparse, json, os, sys, datetime, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import memory_core as mc
import server

ROOT = os.path.dirname(os.path.abspath(__file__))
CASES = json.load(open(os.path.join(ROOT, "student_cases.json"), encoding="utf-8"))
HEDGE = ["不知道", "没有", "无", "不确定", "不清楚", "无法", "没提", "档案里", "无法确定", "不知道", "不太清楚", "我这边没有"]

def build_msgs(system, mem_block, hist, q):
    return [{"role": "system", "content": system + ("\n\n" + mem_block if mem_block else "")}] + hist[-8:] + [{"role": "user", "content": q}]

def _variants(kw):
    """关键词等价变体: 去'的'/空格; 时间 HH:MM → 中文钟点; 小数掌握度 → 百分比"""
    vs = {kw, kw.replace("的", "")}
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", kw)
    if m:
        h, mi = int(m.group(1)), m.group(2)
        h12 = h - 12 if h > 12 else h
        vs |= {f"{h}点", f"{h}:{mi}"}
        if mi == 0:
            vs |= {f"{h12}点", f"下午{h12}点", f"下午{h12}点到{h12+1}点"}
        elif mi == 30:
            vs |= {f"{h12}点半", f"下午{h12}点半"}
    m = re.fullmatch(r"0\.(\d)(\d)", kw)
    if m:
        vs.add(f"{int(m.group(1)+m.group(2))}%")
        vs.add(f"{int(m.group(1)+m.group(2))}％")
    return {v for v in vs if v}

def score_probe(p, ans):
    if p["type"] == "trap":
        hedged = any(w in ans for w in HEDGE)
        # 编造痕迹: 给了具体新数字/名字且未回避
        return (1 if hedged else 0), (not hedged)
    ans_n = ans.replace(" ", "").replace("的", "")  # expect 关键词均不含"的", 容许回述加"的"
    hits = sum(1 for k in p["expect"] if any(v in ans_n for v in _variants(k)))
    return (1 if hits == len(p["expect"]) else (0.5 if hits > 0 else 0)), False

def run_case(case, model, with_dialogue=True, log=None):
    SYSTEM = "你是一位耐心的中小学辅导老师。你手上有一份学生档案和辅导记忆。回答以档案与记忆为准，没有的信息要明说不知道，不要编造。"
    store = mc.MemoryStore()
    history = []
    sid = case["student"]["id"]

    # T0: 档案注入
    intro = "老师好，这是我的档案，麻烦您看一下：" + case["dossier"]
    reply = server.call_llm(build_msgs(SYSTEM, "", [], intro))
    history += [{"role": "user", "content": intro}, {"role": "assistant", "content": reply}]
    store.save(intro, 0, "学生"); store.save(reply, 0, "老师")
    print(f"[{sid}] 档案注入完成", flush=True)

    # T1..N: MathDial 重放
    if with_dialogue:
        md = case["mathdial"]
        sq = f"老师，这道题我不会：{md['question']} 我的解法是：{md['incorrect_solution']}"
        for ti, text in enumerate([sq] + md["student_turns"], start=1):
            ans = server.call_llm(build_msgs(SYSTEM, mc.default_memory_block(store), history, text)) or ""
            history += [{"role": "user", "content": text}, {"role": "assistant", "content": ans}]
            k, dr = store.save(text, ti, "学生"); store.save(ans, ti, "老师")
            if log: log.write(json.dumps({"case": sid, "turn": ti, "q": text[:100], "a": ans[:150]}, ensure_ascii=False) + "\n"); log.flush()
            print(f"[{sid}|{model}] turn {ti} (kept {len(k)}, dropped {len(dr)})", flush=True)

    org, _ = mc.organize(store, lambda p: server.call_llm([{"role": "user", "content": p}]))
    comp, _ = mc.compress(store, lambda p: server.call_llm([{"role": "user", "content": p}]))
    print(f"[{sid}] raw={len(store.raw_text())} org={len(org)} comp={len(comp)}", flush=True)

    strategies = {"raw": "【长期记忆·原始保存】\n" + store.raw_text(),
                  "organized": "【长期记忆·整理版】\n" + org,
                  "compressed": "【长期记忆·压缩版】\n" + comp}
    results = {}
    for sname, block in strategies.items():
        per_type = {}
        for p in case["probes"]:
            ans = server.call_llm(build_msgs(SYSTEM, block, [], p["q"])) or ""
            sc, hal = score_probe(p, ans)
            per_type.setdefault(p["type"], []).append(sc)
            if log:
                log.write(json.dumps({"case": sid, "strategy": sname, "pid": p["pid"],
                                      "type": p["type"], "score": sc, "halluc": hal, "ans": ans[:200]}, ensure_ascii=False) + "\n"); log.flush()
            print(f"[{sid}|{model}|{sname}] {p['pid']}: {sc}{' HALLUC!' if hal else ''}", flush=True)
        results[sname] = {t: round(sum(v) / len(v), 3) for t, v in per_type.items()}
        results[sname]["ctx_chars"] = len(block)
    return {"case": sid, "name": case["student"]["name"], "results": results,
            "sizes": {"raw": len(store.raw_text()), "organized": len(org), "compressed": len(comp)},
            "save_stats": store.stats}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--cases", type=int, default=5)
    ap.add_argument("--no-dialogue", action="store_true", help="只注入档案+探针, 跳过对话重放(快速验证)")
    a = ap.parse_args()
    server.CFG["api_key"] = os.environ.get("OPENCODE_API_KEY", "")  # 脱敏: 从环境变量读取
    server.CFG["model"] = a.model
    tag = datetime.datetime.now().strftime("%m%d_%H%M%S")
    out = os.path.join(ROOT, "..", "..", "results", f"cases_{a.model}_{tag}.jsonl")
    log = open(out, "w", encoding="utf-8")
    allr = []
    for case in CASES[:a.cases]:
        allr.append(run_case(case, a.model, not a.no_dialogue, log))
        log.write(json.dumps({"case_summary": allr[-1]}, ensure_ascii=False) + "\n"); log.flush()
    # 聚合
    agg = {}
    for r in allr:
        for sname, res in r["results"].items():
            for t, v in res.items():
                if t == "ctx_chars": continue
                agg.setdefault(sname, {}).setdefault(t, []).append(v)
    summary = {"model": a.model, "n_cases": len(allr),
               "agg": {s: {t: round(sum(v) / len(v), 3) for t, v in d.items()} for s, d in agg.items()},
               "per_case": allr}
    log.write(json.dumps({"SUMMARY": summary}, ensure_ascii=False) + "\n"); log.close()
    print("AGG:", json.dumps(summary["agg"], ensure_ascii=False, indent=1), flush=True)

if __name__ == "__main__":
    main()
