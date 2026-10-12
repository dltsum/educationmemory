# -*- coding: utf-8 -*-
"""E2E: 模拟前端完整流程 — config(新字段) → 3轮对话 → organize → compress → memory 快照校验"""
import requests, json, os
B = "http://127.0.0.1:8766"
KEY = os.environ.get("OPENCODE_API_KEY", "")  # 脱敏: 从环境变量读取

# 1. config 新字段
r = requests.post(B + "/config", json={"api_key": KEY, "model": "mimo-v2.5", "variant": "", "max_tokens": "4000", "temperature": ""})
assert r.json()["ok"], r.text
r = requests.post(B + "/config", json={"evil_key": "x", "max_tokens": "6000"})
assert r.json()["ok"]
print("[1] config OK (新字段+非法字段过滤)")

# 2. 三轮对话(含档案注入)
qs = ["老师好，这是我的档案：我叫林晓芸，五年级2班，掌握度最低的是单位换算0.30，前置是乘法口诀。我最活跃提问时段17:30-19:00，最近四周分数加减提问9次。",
      "分数加减里 1/2+1/3 我总是算成 2/5，为什么错了？",
      "嗯嗯好的，谢谢老师！那我该先补什么？"]
hist = []
for i, q in enumerate(qs, 1):
    msgs = [{"role": "system", "content": "你是耐心的辅导老师"}] + hist + [{"role": "user", "content": q}]
    r = requests.post(B + "/chat", json={"messages": msgs, "question": q, "turn_no": i})
    d = r.json(); assert d.get("reply"), f"turn{i} 空回复"
    hist += [{"role": "user", "content": q}, {"role": "assistant", "content": d["reply"]}]
    print(f"[2.{i}] reply {len(d['reply'])}ch, kept {len(d['saved']['kept'])}, dropped {len(d['saved']['dropped'])}")

# 3. 整理
r = requests.post(B + "/organize"); d = r.json()
org = d["memory"]["organized"]; assert d["changed"] and len(org) > 100, "organize 未生效"
assert "[T" in org, "整理缺 [T#] 来源"
print(f"[3] organize OK changed={d['changed']} {d['memory']['stats']['raw_chars']}→{len(org)}ch")

# 4. 压缩
r = requests.post(B + "/compress"); d = r.json()
comp = d["memory"]["compressed"]; assert len(comp) > 50, "compress 未生效"
print(f"[4] compress OK {len(org)}→{len(comp)}ch ({100 - len(comp) * 100 // len(org)}%↓)")

# 5. best_block 信任标注 + 探针召回
bb = d["memory"]["best_block"]
assert "可能过时" in bb and "明说不知道" in bb, "best_block 缺信任标注"
assert bb.startswith("【长期记忆·压缩版】"), "best_block 应优先压缩层"
msgs = [{"role": "system", "content": "你是耐心的辅导老师\n\n" + bb},
        {"role": "user", "content": "我掌握最弱的知识点是什么？我最活跃提问时段是几点开始？"}]
r = requests.post(B + "/chat", json={"messages": msgs, "question": "probe", "turn_no": 9})
ans = r.json()["reply"]
ok = ("单位换算" in ans) and ("17:30" in ans or "17点半" in ans or "5点半" in ans)
print(f"[5] best_block 探针: {'PASS' if ok else 'FAIL'} :: {ans[:120]}")
requests.post(B + "/reset")
print("ALL E2E PASS" if ok else "E2E DONE (probe FAIL)")
