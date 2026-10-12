# -*- coding: utf-8 -*-
"""三层记忆辅导台 高压测试
A. 快速连发: 3个学生 × (档案+4问) 无间隔连发, 验证回复非空+记忆持续增长
B. 并发突发: 同一后端 4 线程并发 /chat, 验证全部 200 且记忆不丢不错乱
C. 全风格压测: 7 风格逐一 整理+压缩, 计时+验证产出非空、字符数下降
D. 压后探针: 高压后问档案事实, 验证记忆未损坏(关键词命中)
退出码: 0=全过, 1=有失败 (显式失败原则, 无兜底)
"""
import json, time, sys, threading, requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8766"
DEMOS = requests.get(f"{BASE}/demos", timeout=10).json()["demos"]
STYLES = requests.get(f"{BASE}/memory", timeout=10).json()["styles"]
results = []  # (phase, name, ok, detail)

def best_block():
    return requests.get(f"{BASE}/memory", timeout=10).json().get("best_block") or ""

def chat(question, messages=None, timeout=180):
    if messages is None:
        # 与前端 _sysMsg 一致: 最优记忆块注入 system, 再接用户问题
        messages = [{"role": "system", "content": "你是一位耐心的一对一辅导老师。以下是该学生的记忆档案：\n" + best_block()},
                    {"role": "user", "content": question}]
    r = requests.post(f"{BASE}/chat", json={
        "messages": messages,
        "question": question, "turn_no": 1}, timeout=timeout)
    r.raise_for_status()
    return r.json()

def reset():
    requests.post(f"{BASE}/reset", timeout=10)

def stats():
    m = requests.get(f"{BASE}/memory", timeout=10).json()
    return m["stats"]

def rec(phase, name, ok, detail=""):
    results.append((phase, name, ok, detail))
    print(f"[{phase}] {'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)

# D 单跑模式提前拦截(避免连带跑 A/B/C 高压段)
if len(sys.argv) > 1 and sys.argv[1] == "D":
    ONLY_D = True
else:
    ONLY_D = False

# ---------- A. 快速连发 ----------
if ONLY_D:
    print("=== D 压后探针 (默认风格重建后) ===", flush=True)
    reset()
    chat("老师好，这是我的档案：" + DEMOS[0]["dossier"])
    requests.post(f"{BASE}/config", json={"style": STYLES[0]}, timeout=10)
    requests.post(f"{BASE}/organize", timeout=180)
    requests.post(f"{BASE}/compress", timeout=180)
    s = stats()
    print(f"重建后: 整理{s['organized_chars']}ch 压缩{s['compressed_chars']}ch", flush=True)
    probes = [("我家里为什么没养宠物？", ["猫毛", "过敏"]),
              ("我的球衣号码是多少？", ["7"]),
              ("我最活跃的学习时段是几点到几点？", ["17:30", "19:00"])]
    for q, kws in probes:
        try:
            r = chat(q)["reply"]
            hit = all(k in r for k in kws)
            rec("D", q[:14], hit, f"期望{kws} → {r[:60]}…")
        except Exception as e:
            rec("D", q[:14], False, f"异常: {e}")
    reset()
    fails = [r for r in results if not r[2]]
    print(f"\n===== D 汇总: {len(results)-len(fails)}/{len(results)} 通过 =====")
    sys.exit(1 if fails else 0)

print("=== A 快速连发 (3学生×5次调用, 无间隔) ===", flush=True)
for di in range(3):
    d = DEMOS[di]
    reset()
    t0 = time.time()
    try:
        r1 = chat("老师好，这是我的档案：" + d["dossier"])
        ok1 = len(r1["reply"]) > 50
        s1 = stats()["n_items"]
        lats = [time.time() - t0]
        prev = s1
        mono = True
        for q in d["questions"][:4]:
            tq = time.time()
            r = chat(q)
            lats.append(time.time() - tq)
            if len(r["reply"]) < 10:
                mono = False
            cur = stats()["n_items"]
            if cur <= prev:
                mono = False
            prev = cur
        rec("A", d["name"], ok1 and mono,
            f"条目{s1}→{prev} 延迟avg{sum(lats)/len(lats):.1f}s max{max(lats):.1f}s")
    except Exception as e:
        rec("A", d["name"], False, f"异常: {e}")

# ---------- B. 并发突发 ----------
print("=== B 并发突发 (4线程同时打 /chat) ===", flush=True)
d = DEMOS[0]
reset()
chat("老师好，这是我的档案：" + d["dossier"])
before = stats()["n_items"]
outs, errs = [None] * 4, [None] * 4
qs = ["通分怎么找共同分母？", "我最弱的知识点是什么？", "我什么时候学习效率最高？", "1/2+1/3 等于多少？"]
def worker(i):
    try:
        outs[i] = chat(qs[i])["reply"]
    except Exception as e:
        errs[i] = str(e)
ts = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
t0 = time.time()
[t.start() for t in ts]
[t.join(timeout=200) for t in ts]
dur = time.time() - t0
after = stats()["n_items"]
nok = sum(1 for o in outs if o and len(o) > 10)
rec("B", "并发4请求", nok == 4 and after > before,
    f"成功{nok}/4 耗时{dur:.1f}s 条目{before}→{after} 错误:{[e for e in errs if e] or '无'}")

# ---------- C. 全风格 整理+压缩 ----------
print("=== C 全风格压测 (7风格×整理+压缩) ===", flush=True)
for st in STYLES:
    requests.post(f"{BASE}/config", json={"style": st}, timeout=10)
    try:
        t0 = time.time()
        ro = requests.post(f"{BASE}/organize", timeout=180).json()
        t1 = time.time()
        rc = requests.post(f"{BASE}/compress", timeout=180).json()
        t2 = time.time()
        s = stats()
        ok = (s["organized_chars"] > 100 and s["compressed_chars"] > 50
              and s["compressed_chars"] < s["organized_chars"])
        rec("C", st, ok,
            f"整理{s['organized_chars']}ch({t1-t0:.0f}s) 压缩{s['compressed_chars']}ch({t2-t1:.0f}s) -{100*(1-s['compressed_chars']/max(s['organized_chars'],1)):.0f}%")
    except Exception as e:
        rec("C", st, False, f"异常: {e}")
requests.post(f"{BASE}/config", json={"style": STYLES[0]}, timeout=10)  # 回默认

# ---------- D. 压后探针 (记忆完整性) ----------
# 单跑: python stress_test.py D  → 用默认风格重做 整理+压缩 后探测(模拟真实演示路径)
if len(sys.argv) > 1 and sys.argv[1] == "D":
    results.clear()
    print("=== D 压后探针 (默认风格重建后) ===", flush=True)
    reset()
    chat("老师好，这是我的档案：" + DEMOS[0]["dossier"])
    requests.post(f"{BASE}/config", json={"style": STYLES[0]}, timeout=10)
    requests.post(f"{BASE}/organize", timeout=180)
    requests.post(f"{BASE}/compress", timeout=180)
    s = stats()
    print(f"重建后: 整理{s['organized_chars']}ch 压缩{s['compressed_chars']}ch", flush=True)
    probes = [("我家里为什么没养宠物？", ["猫毛", "过敏"]),
              ("我的球衣号码是多少？", ["7"]),
              ("我最活跃的学习时段是几点到几点？", ["17:30", "19:00"])]
    for q, kws in probes:
        try:
            r = chat(q)["reply"]
            hit = all(k in r for k in kws)
            rec("D", q[:14], hit, f"期望{kws} → {r[:60]}…")
        except Exception as e:
            rec("D", q[:14], False, f"异常: {e}")
    reset()
    fails = [r for r in results if not r[2]]
    print(f"\n===== D 汇总: {len(results)-len(fails)}/{len(results)} 通过 =====")
    sys.exit(1 if fails else 0)

print("=== D 压后探针 ===", flush=True)
probes = [("我家里为什么没养宠物？", ["猫毛", "过敏"]),
          ("我的球衣号码是多少？", ["7"]),
          ("我最活跃的学习时段是几点到几点？", ["17:30", "19:00"])]
for q, kws in probes:
    try:
        r = chat(q)["reply"]
        hit = all(k in r for k in kws)
        rec("D", q[:14], hit, f"期望{kws} → {r[:60]}…")
    except Exception as e:
        rec("D", q[:14], False, f"异常: {e}")

reset()
# ---------- 汇总 ----------
fails = [r for r in results if not r[2]]
print(f"\n===== 高压测试汇总: {len(results)-len(fails)}/{len(results)} 通过 =====")
for p, n, ok, d in fails:
    print(f"  FAIL [{p}] {n}: {d}")
sys.exit(1 if fails else 0)
