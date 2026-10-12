# -*- coding: utf-8 -*-
"""
v2 后端: 三层记忆 + LLM 代理 + 静态页
运行: python server.py  →  http://127.0.0.1:8766
"""
import json, os, time, threading
import requests  # urllib 走系统代理会被网关 403, 必须用 requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import memory_core as mc
import memory_styles as ms

ROOT = os.path.dirname(os.path.abspath(__file__))
STORE = mc.MemoryStore()
# variant = 推理变体 (OpenCode 内置: Anthropic high/max; OpenAI none~xhigh; Google low/high)
def _local_key():  # 本地演示 key: 放在 config.local.json (已 gitignore, 不入库)
    try: return json.load(open(os.path.join(ROOT, "config.local.json"), encoding="utf-8")).get("api_key", "")
    except Exception: return ""
CFG = {"api_key": os.environ.get("OPENCODE_API_KEY") or _local_key(),  # 环境变量优先, 前端可改
       "base_url": "https://opencode.ai/zen/go/v1/chat/completions",
       "model": "mimo-v2.5", "variant": "", "max_tokens": "4000", "temperature": "",
       "style": ms.DEFAULT_STYLE}  # 记忆风格 (memory_styles.STYLES)
LOCK = threading.Lock()

# 演示方案: 复用测试用例集 (dossier + 示例问题), 无文件则退化为空
def load_demos():
    p = os.path.join(ROOT, "testcases", "student_cases.json")
    try:
        cases = json.load(open(p, encoding="utf-8"))
        out = []
        for c in cases:
            md = c["mathdial"]
            # 预设问题文本: 错题开场(完整题目+错误解法) → MathDial 真实多轮追问 → 档案探针
            qs = [f"老师，这道题我不会：{md['question']} 我的解法是：{md['incorrect_solution']}"]
            qs += md.get("student_turns", [])
            qs += [p["q"] for p in c["probes"]]
            out.append({"id": c["student"]["id"], "name": c["student"]["name"],
                        "label": f"{c['student']['id']} {c['student']['name']} · {c['student']['grade']} · {c['student']['personality']['type']}",
                        "dossier": "老师好，这是我的档案，麻烦您看一下：\n" + c["dossier"],
                        "zpd": c.get("zpd_script", []),
                        "exams": c.get("exams", {"src": "", "qs": []}),
                        "questions": qs})
        return out
    except Exception:
        return []
DEMOS = load_demos()

_LAST_CALL = [0.0]

def call_llm(messages, max_tokens=None):
    # 限流阀门: 两次调用至少间隔 2s
    wait = 2 - (time.time() - _LAST_CALL[0])
    if wait > 0:
        time.sleep(wait)
    payload = {"model": CFG["model"], "messages": messages,
               "max_tokens": int(max_tokens or CFG.get("max_tokens") or 4000)}
    if CFG.get("variant"):
        payload["reasoning_effort"] = CFG["variant"]  # OpenCode 内置变体
    if CFG.get("temperature"):
        try:
            payload["temperature"] = float(CFG["temperature"])
        except ValueError:
            pass
    for i in range(6):
        _LAST_CALL[0] = time.time()
        try:
            r = requests.post(CFG["base_url"], json=payload,
                              headers={"Authorization": f"Bearer {CFG['api_key']}",
                                       "x-opencode-session": "structuredmemory-v2"},  # 网关路由要求
                              timeout=240)
            r.raise_for_status()
            out = r.json()["choices"][0]["message"].get("content") or ""
            if out.strip():
                return out
            print(f"[LLM 空回复, 重试 {i+1}/6]")
        except Exception as e:
            print(f"[LLM 重试 {i+1}/6] {e}")
        time.sleep(min(60, 8 * (2 ** i)))  # 指数退避, 抗限流
    return ""

def snapshot():
    return {
        "raw_items": STORE.items,
        "raw_text": STORE.raw_text(),
        "organized": STORE.organized,
        "compressed": STORE.compressed,
        "best_block": ms.block_with(STORE, CFG.get("style") or ms.DEFAULT_STYLE),  # 按当前风格构造, 带信任标注
        "style": CFG.get("style"), "styles": list(ms.STYLES),
        "stats": dict(STORE.stats, n_items=len(STORE.items),
                      raw_chars=len(STORE.raw_text()),
                      organized_chars=len(STORE.organized),
                      compressed_chars=len(STORE.compressed)),
    }

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except UnicodeDecodeError:  # 兼容 GBK 客户端
            return json.loads(raw.decode("gbk", errors="replace") or "{}")

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            b = open(os.path.join(ROOT, "index.html"), "rb").read()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        elif self.path == "/memory":
            self._json(snapshot())
        elif self.path == "/demos":
            self._json({"demos": DEMOS, "has_key": bool(CFG["api_key"])})
        elif self.path == "/config":
            self._json(CFG)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        global STORE
        if self.path == "/config":
            b = self._body()
            CFG.update({k: v for k, v in b.items() if k in CFG and isinstance(v, str)})
            if CFG.get("style") not in ms.STYLES:
                CFG["style"] = ms.DEFAULT_STYLE
            self._json({"ok": True, "model": CFG["model"], "base_url": CFG["base_url"], "style": CFG["style"]})
        elif self.path == "/chat":
            # messages 由前端 buildContext 构造(默认或自定义); turn_no/question 用于记忆保存
            b = self._body()
            with LOCK:
                reply = call_llm(b.get("messages", []))
                turn = b.get("turn_no", len(STORE.items))
                kept_u, drop_u = STORE.save(b.get("question", ""), turn, "学生")
                kept_a, drop_a = STORE.save(reply, turn, "老师")
                self._json({"reply": reply, "memory": snapshot(),
                            "saved": {"kept": kept_u + kept_a, "dropped": [(s, r) for s, r in drop_u + drop_a]}})
        elif self.path == "/organize":
            with LOCK:
                new, changed = ms.organize_with(STORE, lambda msgs: call_llm([{"role": "user", "content": msgs}]), CFG["style"])
                self._json({"changed": changed, "memory": snapshot()})
        elif self.path == "/compress":
            with LOCK:
                new, changed = ms.compress_with(STORE, lambda msgs: call_llm([{"role": "user", "content": msgs}]), CFG["style"])
                self._json({"changed": changed, "memory": snapshot()})
        elif self.path == "/reset":
            with LOCK:
                STORE = mc.MemoryStore()
                self._json({"ok": True, "memory": snapshot()})
        else:
            self.send_response(404); self.end_headers()

if __name__ == "__main__":
    port = 8766
    print(f"v2 三层记忆服务: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
