# -*- coding: utf-8 -*-
"""
================================================================================
 中小学个性化辅导 · 结构化流程记忆 (PSM) 一体化脚本
================================================================================
【快速开始 — 只需填写下面 3 项, 然后运行: python tutor_memory.py】

  API_KEY   : 你的 API 密钥
  BASE_URL  : OpenAI 兼容接口地址 (已预填 opencode go)
  MODEL     : 模型名 (已测试: mimo-v2.5 / longcat-2.0)

运行后打开浏览器: http://127.0.0.1:8765  即可对话。
================================================================================
"""

# ======================= 【用户填写区】 =======================
import os
API_KEY = os.environ.get("OPENCODE_API_KEY", "")  # 脱敏: 从环境变量读取
BASE_URL = "https://opencode.ai/zen/go/v1/chat/completions"                     # ← 接口地址
MODEL    = "mimo-v2.5"                  # ← 模型: mimo-v2.5 | longcat-2.0

# 记忆模式 (6 选 1):
#   linear     全历史线性叠加 (基线, 幻觉严重, 仅作对照)
#   window     只保留最近 K 轮原文
#   summary    滚动摘要: 旧对话压缩成摘要
#   psm        结构化流程记忆 (推荐★): 学生卡片注入 system 区
#   psm_tail   结构化流程记忆·尾部注入: 学生卡片放在最新消息之前
#   psm_dag    结构化流程记忆 + 知识点前置 DAG 根因追踪
MODE = "psm"

# 教师人设 (可自行修改)
TEACHER_PERSONA = "你是一位耐心的小学数学辅导老师, 讲解适合小学生水平, 多鼓励, 善用生活化例子。"

# 窗口模式的 K (仅 window 模式用)
WINDOW_K = 6

# 知识点前置 DAG (psm_dag 模式用; 可按学科自行扩充)
# 含义: 学 B 之前必须先会 A 记作 "A": ["B"] (A 是 B 的前置)
KNOWLEDGE_DAG = {
    "分数意义": ["分数比较", "分数加减"],
    "通分": ["分数加减", "分数比较"],
    "最小公倍数": ["通分"],
    "分数加减": ["分数乘除", "分数混合运算"],
    "分数乘法": ["分数除法"],
    "分数除法": ["分数乘除"],
    "小数化分数": ["分数乘除"],
    "运算顺序": ["分数混合运算"],
}

# 资源推荐库 (知识点 → 推荐资源, 可自行扩充; 代码查表, 不由模型编造)
RESOURCE_LIB = {
    "最小公倍数": "《短除法求最小公倍数》练习 10 题",
    "通分": "《通分专项练习(基础篇)》",
    "分数加减": "《异分母分数加减》微课 8 分钟",
    "运算顺序": "《混合运算顺序口诀卡片》",
}
# =============================================================

import json, re, os, time, threading, datetime, webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory_state.json")

# ---------------- LLM 调用 (OpenAI 兼容) ----------------
def call_llm(messages, max_tokens=4000):
    body = json.dumps({"model": MODEL, "messages": messages, "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(BASE_URL, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode())
                return d["choices"][0]["message"].get("content") or ""
        except Exception as e:
            print(f"[API 重试 {i+1}/3] {e}")
            time.sleep(3 * (i + 1))
    return "(接口调用失败, 请稍后重试)"

# ---------------- 结构化记忆状态 (PSM) ----------------
EMPTY_STATE = {"student_profile": {}, "knowledge_state": {}, "blind_spots": [], "notes": []}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, encoding="utf-8"))
        except Exception:
            pass
    return json.loads(json.dumps(EMPTY_STATE))

def save_state(s):
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

EXTRACT_PROMPT = """你是记忆抽取器。根据最新一轮对话, 输出对记忆状态的更新, 严格只输出 JSON。
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
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def apply_updates(state, upd):
    for k, v in (upd.get("profile_updates") or {}).items():
        if isinstance(v, str) and v.strip():
            state["student_profile"][k] = v.strip()
    for item in (upd.get("knowledge_updates") or []):
        kc = str(item.get("kc", "")).strip()
        if not kc:
            continue
        ks = state["knowledge_state"].setdefault(kc, {"mastery": 0.5, "errors": 0})
        ks["mastery"] = round(ks["mastery"] + 0.25 * ((1 if item.get("correct") else 0) - ks["mastery"]), 3)
        if not item.get("correct"):
            ks["errors"] += 1
    for k in (upd.get("retract") or []):
        state["student_profile"].pop(k, None)
    for n in (upd.get("notes") or []):
        if isinstance(n, str) and n.strip():
            state["notes"] = (state["notes"] + [n.strip()])[-8:]
    state["blind_spots"] = [k for k, v in state["knowledge_state"].items()
                            if v["mastery"] < 0.6 and v["errors"] >= 2]

def dag_root_causes(state):
    """沿前置 DAG 反向追溯: 盲点知识点的未掌握前置 = 根因候选。"""
    prereq_of = {}
    for pre, posts in KNOWLEDGE_DAG.items():
        for p in posts:
            prereq_of.setdefault(p, []).append(pre)
    roots = []
    for bs in state["blind_spots"]:
        for pre in prereq_of.get(bs, []):
            ks = state["knowledge_state"].get(pre)
            if ks is None or ks["mastery"] < 0.6:
                roots.append(pre)
    seen, out = set(), []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def compile_card(state, with_dag=False):
    """把结构化状态编译成注入上下文的"学生卡片" (纯代码, 无LLM, 杜绝摘要漂移)。"""
    prof = "；".join(f"{k}:{v}" for k, v in state["student_profile"].items()) or "暂无"
    ks = "；".join(f"{k} 掌握度{v['mastery']}(错{v['errors']}次)" for k, v in state["knowledge_state"].items()) or "暂无"
    blind = "、".join(state["blind_spots"]) or "暂无"
    rec = "；".join(f"{k}→{RESOURCE_LIB[k]}" for k in state["blind_spots"] if k in RESOURCE_LIB) or "暂无"
    card = ("【学生卡片】\n"
            f"学生档案: {prof}\n"
            f"知识点状态: {ks}\n"
            f"已识别盲点: {blind}\n"
            f"推荐资源: {rec}\n"
            f"备注: {'；'.join(state['notes'][-3:]) or '暂无'}")
    if with_dag:
        roots = dag_root_causes(state)
        card += f"\n根因前置知识点(需优先补): {'、'.join(roots) if roots else '暂无'}"
    card += "\n(以上卡片是唯一可信的学生信息来源; 卡片中没有的信息, 请明说不知道, 绝不要编造。)"
    return card

# ---------------- 会话 (内存态, 重启保留结构化状态) ----------------
class Session:
    def __init__(self):
        self.history = []          # [{role, content}] 全部原文
        self.summary = ""          # summary 模式的滚动摘要
        self.state = load_state()  # PSM 结构化状态

SESSION = Session()
LOCK = threading.Lock()

def update_memory(student, tutor):
    """每轮对话后更新记忆 (仅需要的模式执行)。"""
    if MODE == "summary":
        old = SESSION.history[:-8]
        if len(old) >= 6:
            txt = "\n".join(f"{'学生' if m['role']=='user' else '老师'}: {m['content'][:200]}" for m in old)
            s = call_llm([{"role": "user", "content":
                f"把以下旧对话压缩成150字内的学生情况摘要, 保留具体事实(姓名/年级/错题/偏好), 只输出摘要:\n旧摘要: {SESSION.summary}\n旧对话:\n{txt}"}])
            if s:
                SESSION.summary = s.strip()
                del SESSION.history[:-6]
    if MODE in ("psm", "psm_tail", "psm_dag"):
        ext = call_llm([{"role": "user", "content": EXTRACT_PROMPT.format(
            state=json.dumps(SESSION.state, ensure_ascii=False)[:1500],
            student=student, tutor=tutor[:500])}])
        upd = parse_json_loose(ext)
        if upd:
            apply_updates(SESSION.state, upd)
            save_state(SESSION.state)
        else:
            print("[警告] 本轮记忆抽取失败, 已跳过 (详见日志)")  # 显式失败

# ============================================================
# 【上下文组装方法 — 可重写槽位】
#   这是整个脚本唯一需要你按自己需求重写的方法。
#   输入: 当前用户消息 + 会话对象; 输出: 发给模型的 messages 列表。
#   ★ 注册结论 (2026-09-02, results/REPORT.md): 结构化学生卡片放在 system 区(模式 psm)
#     为默认。实测 system 区 vs 尾部注入(psm_tail) 在 mimo-v2.5/longcat-2.0 上
#     准确率无显著差异; 选 system 区的理由: 前缀稳定 → 缓存友好、与人设同区、
#     卡片不被后续消息稀释。尾部注入保留为对照模式。
#   其他可自定义插位: 人设 / 卡片文案 / 资源库 / DAG 见脚本头【用户填写区】。
# ============================================================
def build_context(user_msg):
    psm_card = compile_card(SESSION.state, with_dag=(MODE == "psm_dag"))
    if MODE == "linear":
        return [{"role": "system", "content": TEACHER_PERSONA}] + SESSION.history + [{"role": "user", "content": user_msg}]
    if MODE == "window":
        return [{"role": "system", "content": TEACHER_PERSONA}] + SESSION.history[-2 * WINDOW_K:] + [{"role": "user", "content": user_msg}]
    if MODE == "summary":
        sys = TEACHER_PERSONA + (f"\n\n【学生情况摘要】{SESSION.summary}" if SESSION.summary else "")
        return [{"role": "system", "content": sys}] + SESSION.history[-6:] + [{"role": "user", "content": user_msg}]
    if MODE == "psm_tail":
        msgs = [{"role": "system", "content": TEACHER_PERSONA}] + SESSION.history[-4:]
        msgs.append({"role": "user", "content": psm_card + "\n\n" + user_msg})
        return msgs
    # psm / psm_dag: 卡片注入 system 区 (注册默认)
    sys = TEACHER_PERSONA + "\n\n" + psm_card
    return [{"role": "system", "content": sys}] + SESSION.history[-4:] + [{"role": "user", "content": user_msg}]

def chat(user_msg):
    with LOCK:
        msgs = build_context(user_msg)
        ans = call_llm(msgs)
        SESSION.history += [{"role": "user", "content": user_msg}, {"role": "assistant", "content": ans}]
        update_memory(user_msg, ans)
        return ans

# ---------------- Web UI (零依赖) ----------------
PAGE = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>辅导记忆助手</title>
<style>
body{font-family:system-ui,'Microsoft YaHei',sans-serif;margin:0;background:#f5f6f8;display:flex;height:100vh}
#main{flex:1;display:flex;flex-direction:column;max-width:820px;margin:0 auto}
#log{flex:1;overflow-y:auto;padding:16px}
.msg{margin:8px 0;padding:10px 14px;border-radius:12px;max-width:80%;white-space:pre-wrap;word-break:break-word}
.u{background:#dbeafe;margin-left:auto}.a{background:#fff;border:1px solid #e5e7eb}
#bar{display:flex;gap:8px;padding:12px;background:#fff;border-top:1px solid #e5e7eb}
#in{flex:1;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}
button{padding:10px 18px;border:0;border-radius:8px;background:#2563eb;color:#fff;cursor:pointer}
#side{width:300px;background:#fff;border-left:1px solid #e5e7eb;padding:12px;overflow-y:auto;font-size:13px}
pre{white-space:pre-wrap;word-break:break-word}
</style></head><body>
<div id="main"><div id="log"></div>
<div id="bar"><input id="in" placeholder="向老师提问… (回车发送)" autofocus>
<button onclick="send()">发送</button></div></div>
<div id="side"><b>记忆状态 (模式: __MODE__)</b><pre id="st">加载中…</pre></div>
<script>
const log=document.getElementById('log'),inp=document.getElementById('in');
function add(t,c){const d=document.createElement('div');d.className='msg '+c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight}
async function refresh(){try{const r=await fetch('/state');document.getElementById('st').textContent=await r.text()}catch(e){}}
async function send(){const q=inp.value.trim();if(!q)return;inp.value='';add(q,'u');add('思考中…','a');
 const r=await fetch('/chat',{method:'POST',body:JSON.stringify({message:q})});
 const d=await r.json();log.lastChild.textContent=d.reply;refresh()}
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send()});refresh();setInterval(refresh,5000);
</script></body></html>""".replace("__MODE__", MODE)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静音访问日志
        pass
    def _send(self, body, ctype="text/html; charset=utf-8"):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_GET(self):
        if self.path == "/":
            self._send(PAGE)
        elif self.path == "/state":
            if MODE in ("psm", "psm_tail", "psm_dag"):
                self._send(json.dumps(SESSION.state, ensure_ascii=False, indent=2), "text/plain; charset=utf-8")
            elif MODE == "summary":
                self._send("【滚动摘要】\n" + (SESSION.summary or "暂无"), "text/plain; charset=utf-8")
            else:
                self._send(f"【{MODE} 模式】无结构化状态\n历史轮数: {len(SESSION.history)//2}", "text/plain; charset=utf-8")
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == "/chat":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n).decode() or "{}")
            reply = chat(body.get("message", ""))
            self._send(json.dumps({"reply": reply}, ensure_ascii=False), "application/json; charset=utf-8")
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    port = 8765
    print(f"记忆模式: {MODE} | 模型: {MODEL}")
    print(f"打开浏览器访问: http://127.0.0.1:{port}")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
