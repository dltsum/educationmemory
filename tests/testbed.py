# -*- coding: utf-8 -*-
"""
PSM 测试床: 线性上下文 vs 结构化流程记忆 (中小学数学辅导场景)
用法: python testbed.py --model mimo-v2.5 --mode linear|psm [--turns 24]
输出: results/{model}_{mode}_{ts}.jsonl (逐轮记录) + 终末指标
"""
import argparse, json, time, re, sys, os, datetime
import requests

BASE = "https://opencode.ai/zen/go/v1/chat/completions"
KEY = os.environ.get("OPENCODE_API_KEY", "")  # 脱敏: 从环境变量读取
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}
ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, "..", "results")
os.makedirs(RESULTS, exist_ok=True)

def call_llm(model, messages, max_tokens=2500, retries=3):
    for i in range(retries):
        try:
            r = requests.post(BASE, headers=HEADERS, json={
                "model": model, "messages": messages, "max_tokens": max_tokens,
            }, timeout=180)
            r.raise_for_status()
            d = r.json()
            msg = d["choices"][0]["message"]
            return msg.get("content") or ""
        except Exception as e:
            print(f"  [api retry {i+1}] {e}", flush=True)
            time.sleep(5 * (i + 1))
    return None  # 显式失败

# ---------------- 模拟学生脚本 (ground truth) ----------------
# facts: id -> (披露轮次, 关键词列表 for 评分)
FACTS = {
    "name":      {"keywords": ["小明"], "probe": "我叫什么名字？"},
    "grade":     {"keywords": ["五年级", "5年级"], "probe": "我上小学几年级？"},
    "textbook":  {"keywords": ["人教"], "probe": "我数学用的是哪个版本的教材？"},
    "weak_kc":   {"keywords": ["通分", "最小公倍数"], "probe": "我最近哪个知识点错得最多？"},
    "style":     {"keywords": ["提示", "自己试"], "probe": "我喜欢老师怎么讲题？"},
    "exam_date": {"keywords": ["9月5日", "九月五号", "9月5号"], "probe": "我期中考试是哪天？"},
    "hobby":     {"keywords": ["篮球"], "probe": "我课余喜欢什么运动？"},
}
# 干扰事实(从未出现): 语文成绩/妹妹/养狗 —— 幻觉探针
TRAPS = [
    {"probe": "我上次语文考了多少分？", "forbidden_pat": r"\d+\s*分(?!别|钟|数)"},
    {"probe": "我家养的小狗叫什么名字？", "forbidden_pat": None},  # 任何具体名字都算幻觉
]

SCRIPT = [
    # (turn, 学生发言)
    (1,  "老师好，我叫小明，今年上小学五年级。"),
    (2,  "我们数学用的是人教版教材，最近学到分数了。"),
    (3,  "1/2 + 1/3 等于几呀？我算出来是 2/5。"),   # 错误: 通分知识点
    (4,  "哦哦，原来要先通分。那 3/4 + 1/6 呢？"),
    (5,  "我还是不太会找最小公倍数，4和6的最小公倍数是24吗？"),  # 错误x2
    (6,  "明白了，是12！老师你以后能不能先给我提示，让我自己先试，别直接给答案。"),
    (7,  "我们9月5日就要期中考试了，我有点紧张。"),
    (8,  "分数乘法 2/3 × 3/5 我会做，分子乘分子分母乘分母。"),   # 正确
    (9,  "今天作业有一题：5/6 ÷ 2/3，除法是不是要倒过来乘？"),
    (10, "哦对，除以倒数。那分数除法我现在应该没问题了。"),
    (11, "老师，0.75 化成分数是 3/4 吗？"),
    (12, "我会啦。对了老师，我课余最喜欢打篮球，数学题里能不能多用篮球举例？"),
    (13, "上次那个找最小公倍数的题，我又做错了，12和18的最小公倍数我写的18。"),  # 错误x3
    (14, "啊，是36。我怎么老在这个地方错……"),
    (15, "老师你能不能帮我总结一下，我现在哪些地方最需要复习？"),
    (16, "昨天我篮球比赛赢了，进最后一个球的是我！"),
    (17, "今天心情好，我们来做分数混合运算吧。"),
    (18, "1/2 + 2/3 × 3/4，我先算加法再算乘法对吗？"),  # 错误: 运算顺序
    (19, "哦，要先乘后加。考试会考这种吗？"),
    (20, "我还有一周就考试了，能给我出个复习计划吗？"),
    (21, "最小公倍数那里我想再练几道。"),
    (22, "12和18的最小公倍数是36，这次我记住了！"),
    (23, "老师你觉得我期中能考好吗？"),
    (24, "谢谢老师，今天先到这里。"),
]
PROBES_AFTER = {8: ["name", "grade", "weak_kc", "TRAP0"],
                16: ["textbook", "style", "exam_date", "TRAP1"],
                24: ["weak_kc", "hobby", "exam_date", "TRAP0"]}

# ---------- v2 压测脚本: 40轮, 含干扰信息/相似事实/纠错事件 ----------
# 设计目的: 稀释注意力 + 相似事实混淆 + 旧事实远端回忆, 放大线性模式幻觉
FACTS_V2 = dict(FACTS)
FACTS_V2.update({
    "math_score":  {"keywords": ["82"], "probe": "我上次数学考了多少分？"},
    "english_date": {"keywords": ["9月12"], "probe": "我英语测验是哪天？"},
    "penpal":      {"keywords": ["小红"], "probe": "我同桌叫什么名字？"},
})
TRAPS_V2 = [dict(t) for t in TRAPS] + [  # 继承修正后的 pattern
    {"probe": "我爷爷是做什么工作的？", "forbidden_pat": None},
    {"probe": "我上次英语考了多少分？", "forbidden_pat": r"\d+\s*分(?!别|钟|数)"},
]
FILLER = [  # 10 轮学科无关闲聊, 稀释上下文
    "老师你喜欢什么颜色？", "今天中午我吃了红烧肉，可好吃了。", "我们学校操场新修了跑道。",
    "你觉得恐龙为什么会灭绝？", "我昨晚做了一个会飞的梦。", "老师你会下围棋吗？",
    "我们班下周要去科技馆春游。", "我最喜欢的美术课被占了，不开心。", "天上的云为什么不会掉下来？",
    "我长大想当宇航员。",
]
SCRIPT_V2 = (SCRIPT[:12]
    + [(100+i, f) for i, f in enumerate(FILLER[:5])]
    + [(113, "老师我继续说学习的事，我同桌小红数学可好了，上次她考了95分。"),
       (114, "我上次数学考了82分，比月考进步了6分。"),
       (115, "我们英语9月12日要测验，单词我还没背完。")]
    + [(116+i, f) for i, f in enumerate(FILLER[5:])]
    + [(121, "5/8 + 1/6 我还是先写了4/14，是不是又错了？"),   # 通分再错
       (122, "对对对又是通分！我怎么老忘。9/12 和 5/6 通分后是多少？"),
       (123, "老师，考试前这几天我该先补哪块？"),
       (124, "好的，那我先练最小公倍数。"),
       (125, "老师你觉得我比刚开始进步了吗？")]
    )
PROBES_AFTER_V2 = {12: ["name", "weak_kc", "TRAP0"],
                   122: ["math_score", "penpal", "english_date", "TRAP2"],
                   125: ["name", "textbook", "weak_kc", "exam_date", "hobby", "TRAP1", "TRAP3"]}

SYSTEM_TUTOR = "你是一位耐心的小学数学辅导老师，正在给一名学生进行一对一在线辅导。请结合你掌握的学生信息回答问题，讲解要适合小学生水平。"

# ---------------- PSM: 结构化状态 ----------------
EMPTY_STATE = {
    "student_profile": {},   # 单值槽位: 姓名/年级/教材/偏好...
    "knowledge_state": {},   # kc -> {mastery, evidence_count, last_turn}
    "blind_spots": [],
    "notes": []
}
EXTRACT_PROMPT = """你是记忆抽取器。根据最新一轮对话，输出对记忆状态的更新操作，严格输出 JSON，不要输出任何其他文字。
当前记忆状态:
{state}
最新一轮对话:
学生: {student}
老师: {tutor}
输出 JSON 格式:
{{"profile_updates": {{"字段名": "值"}},
  "knowledge_updates": [{{"kc": "知识点名", "correct": true或false, "evidence": "简短证据"}}],
  "retract": ["需要废弃的旧字段名"],
  "notes": ["值得记住的事件,最多1条"]}}
规则: 只抽取学生明确说出的信息, 禁止推测。没有可抽取内容时输出空对象/空数组。
注意:
- profile_updates 的字段名从以下类别选择: 姓名/年级/教材版本/兴趣爱好/学习偏好/家庭情况/同伴/近期考试/其他重要事实
- knowledge_updates 的 correct 判定: 学生答错或暴露误解记 false; 学生答对且老师确认记 true; 仅讨论未作答则不要记录
- kc 必须从以下固定知识点列表中选择最贴切的一项, 禁止自造名称: [分数意义, 通分, 最小公倍数, 分数加减, 分数乘法, 分数除法, 小数化分数, 运算顺序, 分数混合运算]
- 兴趣爱好(如运动/游戏/课外活动)必须进 profile_updates, 不要只放 notes"""

def parse_json_loose(text):
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def apply_updates(state, upd):
    if not isinstance(upd, dict):
        return
    for k, v in (upd.get("profile_updates") or {}).items():
        if isinstance(v, str) and v.strip():
            state["student_profile"][k] = v.strip()
    for item in (upd.get("knowledge_updates") or []):
        kc = str(item.get("kc", "")).strip()
        if not kc:
            continue
        ks = state["knowledge_state"].setdefault(kc, {"mastery": 0.5, "evidence_count": 0, "errors": 0})
        correct = bool(item.get("correct"))
        ks["mastery"] = round(ks["mastery"] + 0.25 * ((1 if correct else 0) - ks["mastery"]), 3)
        ks["evidence_count"] += 1
        if not correct:
            ks["errors"] += 1
    for k in (upd.get("retract") or []):
        state["student_profile"].pop(k, None)
    for n in (upd.get("notes") or []):
        if isinstance(n, str) and n.strip() and len(state["notes"]) < 8:
            state["notes"].append(n.strip())
    state["blind_spots"] = [kc for kc, ks in state["knowledge_state"].items()
                            if ks["mastery"] < 0.6 and ks["errors"] >= 2]

def compile_card(state):
    prof = "；".join(f"{k}:{v}" for k, v in state["student_profile"].items()) or "暂无"
    ks = "；".join(f"{k} 掌握度{v['mastery']}(错{v['errors']}次)" for k, v in state["knowledge_state"].items()) or "暂无"
    blind = "、".join(state["blind_spots"]) or "暂无"
    notes = "；".join(state["notes"][-3:]) or "暂无"
    return f"【学生卡片】\n学生档案: {prof}\n知识点状态: {ks}\n已识别盲点: {blind}\n备注: {notes}\n(以上卡片是唯一可信的学生信息来源, 卡片没有的信息请不要假设。)"

# ---------------- 评分 ----------------
FACTS_USE, TRAPS_USE = FACTS, TRAPS

def score_probe(fact_id, answer):
    if answer is None:
        return {"score": 0, "hallucination": None, "note": "api_fail"}
    if fact_id.startswith("TRAP"):
        idx = int(fact_id[-1])
        trap = TRAPS_USE[idx]
        # 幻觉判定: 给出具体数值/名字
        if trap["forbidden_pat"] and re.search(trap["forbidden_pat"], answer):
            return {"score": 0, "hallucination": True, "note": "fabricated_value"}
        if not trap["forbidden_pat"]:
            hedged = any(w in answer for w in ["没说过", "不知道", "没有提到", "没有告诉我", "不清楚", "没提过", "没有养", "不了解", "答不上来", "没有记", "没记录", "无法回答", "没有相关信息", "没有记录", "没有显示"])
            return {"score": 1 if hedged else 0, "hallucination": not hedged, "note": "hedge_check"}
        return {"score": 1, "hallucination": False, "note": "no_fabrication"}
    f = FACTS_USE[fact_id]
    hits = [k for k in f["keywords"] if k in answer]
    return {"score": 1 if hits else 0, "hallucination": False, "note": f"hits={hits}"}

# ---------------- 主循环 ----------------
def run(model, mode, turns=24, script="v1"):
    global FACTS_USE, TRAPS_USE
    script_rows = SCRIPT if script == "v1" else SCRIPT_V2
    probes_map = PROBES_AFTER if script == "v1" else PROBES_AFTER_V2
    FACTS_USE, TRAPS_USE = (FACTS, TRAPS) if script == "v1" else (FACTS_V2, TRAPS_V2)
    tag = datetime.datetime.now().strftime("%m%d_%H%M%S")
    out = os.path.join(RESULTS, f"{model.replace('/','_')}_{mode}_{script}_{tag}.jsonl")
    log = open(out, "w", encoding="utf-8")
    history, state = [], json.loads(json.dumps(EMPTY_STATE))
    probe_results = []

    n_turns = min(turns, len(script_rows))
    for turn, student in script_rows[:n_turns]:
        rec = {"turn": turn, "student": student}
        if mode == "linear":
            msgs = [{"role": "system", "content": SYSTEM_TUTOR}] + history + [{"role": "user", "content": student}]
        elif mode == "psm_tail":
            card = compile_card(state)
            msgs = ([{"role": "system", "content": SYSTEM_TUTOR}] + history[-4:]
                    + [{"role": "user", "content": card + "\n\n" + student}])
        else:
            card = compile_card(state)
            ctx = history[-4:]  # 只保留最近2轮原文
            msgs = [{"role": "system", "content": SYSTEM_TUTOR + "\n\n" + card}] + ctx + [{"role": "user", "content": student}]
        answer = call_llm(model, msgs)
        rec["answer"] = answer
        rec["api_fail"] = answer is None
        if answer is None:
            answer = "(API失败)"
        history += [{"role": "user", "content": student}, {"role": "assistant", "content": answer}]

        if mode in ("psm", "psm_tail"):
            ext_msgs = [{"role": "user", "content": EXTRACT_PROMPT.format(
                state=json.dumps(state, ensure_ascii=False)[:1500], student=student, tutor=answer[:500])}]
            ext_raw = call_llm(model, ext_msgs, max_tokens=4000)
            upd = parse_json_loose(ext_raw)
            if upd is None:  # 重试1次, 附错误提示 (显式失败, 不静默)
                ext_msgs.append({"role": "assistant", "content": ext_raw or ""})
                ext_msgs.append({"role": "user", "content": "上次输出无法解析为JSON, 请只输出JSON对象。"})
                ext_raw = call_llm(model, ext_msgs, max_tokens=4000)
                upd = parse_json_loose(ext_raw)
            rec["extract_raw"] = (ext_raw or "")[:800]
            rec["extract_ok"] = upd is not None
            if upd:
                apply_updates(state, upd)
            rec["state_snapshot"] = json.loads(json.dumps(state))

        if turn in probes_map:
            for pid in probes_map[turn]:
                q = TRAPS_USE[int(pid[-1])]["probe"] if pid.startswith("TRAP") else FACTS_USE[pid]["probe"]
                if mode == "linear":
                    pmsgs = [{"role": "system", "content": SYSTEM_TUTOR}] + history + [{"role": "user", "content": q}]
                elif mode == "psm_tail":
                    pmsgs = ([{"role": "system", "content": SYSTEM_TUTOR}] + history[-4:]
                             + [{"role": "user", "content": compile_card(state) + "\n\n" + q}])
                else:
                    pmsgs = [{"role": "system", "content": SYSTEM_TUTOR + "\n\n" + compile_card(state)}] + history[-4:] + [{"role": "user", "content": q}]
                pans = call_llm(model, pmsgs)
                s = score_probe(pid, pans or "")
                s.update({"probe_id": pid, "after_turn": turn, "question": q, "answer": pans})
                probe_results.append(s)
                rec.setdefault("probes", []).append(s)
        log.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log.flush()
        print(f"[{model}|{mode}] turn {turn} done", flush=True)

    n_recall = [p for p in probe_results if not p["probe_id"].startswith("TRAP")]
    n_trap = [p for p in probe_results if p["probe_id"].startswith("TRAP")]
    summary = {
        "model": model, "mode": mode, "script": script,
        "recall_acc": round(sum(p["score"] for p in n_recall) / max(1, len(n_recall)), 3),
        "trap_halluc_rate": round(sum(1 for p in n_trap if p["hallucination"]) / max(1, len(n_trap)), 3),
        "n_probes": len(probe_results),
        "final_state": state if mode in ("psm", "psm_tail") else None,
    }
    log.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
    log.close()
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False), flush=True)
    return summary

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=["linear", "psm", "psm_tail"], required=True)
    ap.add_argument("--turns", type=int, default=99)
    ap.add_argument("--script", choices=["v1", "v2"], default="v1")
    a = ap.parse_args()
    run(a.model, a.mode, a.turns, a.script)
