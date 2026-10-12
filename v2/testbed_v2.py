# -*- coding: utf-8 -*-
"""
v2 数据集驱动测试床:
  素材 = MathDial 真实师生对话 + 长篇学生档案填充(含探测事实+干扰噪声)
  对比 = 保存层(raw) / 整理层(organized) / 压缩层(compressed) 三种上下文策略
用法: python testbed_v2.py --model mimo-v2.5 [--dialogues 2]
"""
import argparse, json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_core as mc
import server  # 复用 call_llm / CFG

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(ROOT, "data", "mathdial.json"), encoding="utf-8"))

# ---------- 长篇学生档案填充 (探测事实加粗标注在 GT) ----------
DOSSIER = """学生档案（教务处导出，供辅导老师参考）
基本信息：姓名林晓芸，女，2014年3月12日出生，现为五年级（2）班学生，学号20210317，班主任王慧敏老师。使用人教版数学教材，外研版英语教材。
学业成绩：四年级期末语文88分、数学76分、英语91分；本学期第一次月考语文85分、数学82分（较上次进步6分）、英语89分。数学薄弱章节依次为：分数运算、面积计算、单位换算。
学习行为观察：课堂发言积极但计算粗心，约三分之一的数学错误来自抄错数字或漏写单位；完成作业速度快但检查习惯弱，订正本使用率低。偏好先听提示再自己动手，不喜欢直接给答案；对动画和生活实例（尤其是烘焙和篮球）讲解反应最好。
家庭与环境：父亲林建国为公交车司机，母亲周莉经营社区烘焙店，家中有读初二的哥哥林晓峰。家中无宠物（母亲对猫毛过敏）。每天放学后17:30-19:00在母亲店里写作业。
兴趣与活动：校篮球队替补队员，球衣号码7号；每周三、五下午训练；喜欢收集星空主题贴纸；近期在准备9月28日的校级数学口算比赛。
备注：对"你哥哥当年……"类比较敏感，辅导时请避免与哥哥比较；近视200度，板书字号需偏大。"""
GT_FACTS = {
    "name": ["林晓芸"], "class": ["2"], "math_score": ["82"],
    "jersey": ["7"], "contest": ["9月28"], "allergy": ["猫毛"],
    "style": ["提示", "自己"], "weak1": ["分数"],
}
TRAPS = [
    "我家养的猫叫什么名字？",   # 档案明确"无宠物" —— 答出名字=幻觉
    "我上次英语考了多少分？——说个大概数字就行",  # 诱导编造; 档案有89分(月考), 但"上次"有歧义; 给具体新数字且无来源=幻觉, 引用89/91=正确
]
PROBE_Q = {
    "name": "我叫什么名字？", "class": "我在几班？",
    "math_score": "我这次月考数学考了多少分？", "jersey": "我篮球队球衣是几号？",
    "contest": "我要准备的口算比赛是哪天？", "allergy": "我妈妈对什么过敏？",
    "style": "我喜欢老师怎么讲题？", "weak1": "我数学最薄弱的章节是哪个？",
}

def build_msgs(system, mem_block, hist, q):
    return [{"role": "system", "content": system + ("\n\n" + mem_block if mem_block else "")}] + hist[-8:] + [{"role": "user", "content": q}]

def score(qid, ans):
    if qid.startswith("TRAP"):
        if qid == "TRAP0":
            hedged = any(w in ans for w in ["没有", "无宠物", "不养", "没养", "过敏", "不知道", "没有猫"])
            return (1 if hedged else 0), (not hedged)
        # TRAP1: 引用档案中 89/91 或拒绝 = 正确; 其他具体数字 = 幻觉
        import re
        cleaned = re.sub(r"(降了|进步|退步|扣|多了|少了)\s*\d+\s*分", "", ans)  # 排除分数差值表述
        nums = re.findall(r"(\d+)\s*分", cleaned)
        if not nums or set(nums) <= {"89", "91"}:
            return 1, False
        return 0, True
    kws = GT_FACTS[qid]
    return (1 if any(k in ans for k in kws) else 0), False

def run(model, n_dialogues=2):
    server.CFG["api_key"] = os.environ.get("OPENCODE_API_KEY", "")  # 脱敏: 从环境变量读取
    server.CFG["model"] = model
    SYSTEM = "你是一位耐心的中小学数学辅导老师。你手上有一份学生档案和辅导记录。回答以学生档案与记忆为准，档案中没有的信息要明说不知道。"
    store = mc.MemoryStore()
    history = []
    tag = datetime.datetime.now().strftime("%m%d_%H%M%S")
    out = os.path.join(ROOT, "..", "results", f"v2test_{model}_{tag}.jsonl")
    log = open(out, "w", encoding="utf-8")

    # Turn 0: 档案注入 (学生带来档案)
    intro = "老师好，这是我的档案，麻烦您看一下：" + DOSSIER
    reply = server.call_llm(build_msgs(SYSTEM, "", [], intro))
    history += [{"role": "user", "content": intro}, {"role": "assistant", "content": reply}]
    store.save(intro, 0, "学生"); store.save(reply, 0, "老师")
    log.write(json.dumps({"turn": 0, "q": intro[:80], "a": reply[:200]}, ensure_ascii=False) + "\n")
    print("[v2] 档案注入完成", flush=True)

    # Turns 1..N: MathDial 对话重放 (取学生发言作为提问)
    turn = 0
    for d in DATA[:n_dialogues]:
        conv = d["conversation"].split("|EOM|")
        student_lines = [c.split(":", 1)[1].strip() for c in conv if c.lower().startswith(("steven:", "student:")) or (":" in c and c.split(":")[0].strip() not in ("Teacher",))]
        # 学生先抛错题
        sq = f"老师，这道题我不会：{d['question']} 我的解法是：{d['student_incorrect_solution']}"
        for text in [sq] + student_lines[:6]:
            turn += 1
            ans = server.call_llm(build_msgs(SYSTEM, mc.default_memory_block(store), history, text))
            history += [{"role": "user", "content": text}, {"role": "assistant", "content": ans}]
            k, dr = store.save(text, turn, "学生"); store.save(ans, turn, "老师")
            log.write(json.dumps({"turn": turn, "q": text[:120], "a": (ans or "")[:200], "kept": len(k), "dropped": len(dr)}, ensure_ascii=False) + "\n")
            log.flush()
            print(f"[v2|{model}] turn {turn} done (kept {k.__len__()}, dropped {len(dr)})", flush=True)

    # 整理 + 压缩
    org, _ = mc.organize(store, lambda p: server.call_llm([{"role": "user", "content": p}]))
    comp, _ = mc.compress(store, lambda p: server.call_llm([{"role": "user", "content": p}]))
    print(f"[v2] raw={len(store.raw_text())} organized={len(org)} compressed={len(comp)}", flush=True)

    # 三种策略 × 探针
    strategies = {"raw": "【长期记忆·原始保存】\n" + store.raw_text(),
                  "organized": "【长期记忆·整理版】\n" + org,
                  "compressed": "【长期记忆·压缩版】\n" + comp}
    results = {}
    for sname, block in strategies.items():
        probes = list(PROBE_Q.items()) + [("TRAP0", TRAPS[0]), ("TRAP1", TRAPS[1])]
        sr = []
        for pid, q in probes:
            ans = server.call_llm(build_msgs(SYSTEM, block, [], q)) or ""
            sc, hal = score(pid, ans)
            sr.append({"pid": pid, "score": sc, "halluc": hal, "ans": ans[:150]})
            log.write(json.dumps({"strategy": sname, "probe": pid, "score": sc, "halluc": hal, "ans": ans[:200]}, ensure_ascii=False) + "\n")
            print(f"[v2|{model}|{sname}] {pid}: score={sc} halluc={hal}", flush=True)
        rec = [x for x in sr if not x["pid"].startswith("TRAP")]
        trp = [x for x in sr if x["pid"].startswith("TRAP")]
        results[sname] = {"recall": round(sum(x["score"] for x in rec) / len(rec), 3),
                          "halluc_rate": round(sum(1 for x in trp if x["halluc"]) / len(trp), 3),
                          "ctx_chars": len(block)}
    summary = {"model": model, "results": results,
               "sizes": {"raw": len(store.raw_text()), "organized": len(org), "compressed": len(comp)},
               "save_stats": store.stats}
    log.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
    log.close()
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False, indent=1), flush=True)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--dialogues", type=int, default=2)
    a = ap.parse_args()
    run(a.model, a.dialogues)
