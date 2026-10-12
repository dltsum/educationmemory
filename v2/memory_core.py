# -*- coding: utf-8 -*-
"""
记忆三层机制核心 (v2)
  1. 记忆保存 save_filter: 本地过滤, 无外部API, 无强规则槽位
     语义 = "过滤掉噪声" 而非 "只保留槽位": 默认全保留, 仅剔除 {重复, 纯应答, 样板话}
  2. 记忆整理 organize: 调用 LLM 把过滤后的原始记忆整理为结构化上下文
  3. 记忆压缩 compress: 调用 LLM 把结构化记忆进一步压缩为高密度导航式摘要
     (参考 Codex memory_summary.md: dense / navigational / discriminative + no-op 门控)
"""
import re, json, hashlib, time

# ---------------- 1. 记忆保存 (本地, 无API) ----------------

_SENT_SPLIT = re.compile(r"(?<=[。！？；!?\n;])|(?<=\.)\s+")

# 纯应答/客套词表 (子句级: 整句所有子句都是应答词才删 —— 宁可漏删不可误删)
_ACK_WORDS = {"嗯", "哦", "噢", "啊", "哈哈", "好", "好的", "好哒", "行", "可以", "谢谢", "谢谢老师", "谢谢你",
              "感谢", "明白", "明白了", "知道", "知道了", "懂", "懂了", "对", "是", "是的", "没错", "好的老师",
              "okay", "ok", "yes", "yeah", "sure", "thanks", "thankyou", "gotit", "isee",
              "老师好", "您好", "你好", "再见", "拜拜", "辛苦老师了", "老师辛苦了"}

def _is_ack(s):
    clauses = [c for c in re.split(r"[,，、!！~～.。]+", _norm(s)) if c]
    return bool(clauses) and all(c in _ACK_WORDS for c in clauses)

# AI 样板话前缀 (助手输出的无信息开场)
_BOILER = re.compile(
    r"^(作为(一名|一个)?AI|作为人工智能|当然可以[，,]?\s*我很乐意|很高兴(为你|帮您|帮助你)|"
    r"以下是|综上所述|总而言之|希望对你有帮助|如果还有问题)")

# 敏感信息脱敏 (参考 Codex: never store tokens/keys/passwords → [REDACTED_SECRET])
_SECRET = [
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"(密码|口令|password|passwd|pwd)\s*[:：是]?\s*\S{4,}", re.I), r"\1: [REDACTED_SECRET]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[REDACTED_IDCARD]"),
]

def _redact(s):
    for pat, rep in _SECRET:
        s = pat.sub(rep, s)
    return s

def _norm(s):
    return re.sub(r"[\s，。！？,.!?~～、；;\"'\"'（）()…—-]+", "", s).lower()

def _ngrams(s, n=3):
    s = _norm(s)
    return {s[i:i+n] for i in range(max(1, len(s)-n+1))} if s else set()

def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

class MemoryStore:
    """原始记忆条目库: [{id, text, turn, role, ts}] + organized + compressed 三层共存"""

    def __init__(self):
        self.items = []            # 保存层输出
        self.organized = ""        # 整理层输出
        self.compressed = ""       # 压缩层输出
        self._ngram_index = []     # 与 items 对齐的 3-gram 集
        self.stats = {"dropped_dup": 0, "dropped_ack": 0, "dropped_boiler": 0, "kept": 0}

    def save(self, text, turn, role, fuzzy_thresh=0.85):
        """过滤后入库。返回 (kept_list, dropped_list) 供 UI 展示。"""
        kept, dropped = [], []
        text = _redact(text)
        for sent in _SENT_SPLIT.split(text):
            s = sent.strip()
            if not s or len(_norm(s)) < 2:
                continue
            if _is_ack(s):
                dropped.append((s, "纯应答")); self.stats["dropped_ack"] += 1; continue
            if _BOILER.match(s):
                dropped.append((s, "样板话")); self.stats["dropped_boiler"] += 1; continue
            ng = _ngrams(s)
            if any(_jaccard(ng, old) >= fuzzy_thresh for old in self._ngram_index):
                dropped.append((s, "重复")); self.stats["dropped_dup"] += 1; continue
            item = {"id": hashlib.md5(f"{turn}{role}{s}".encode()).hexdigest()[:8],
                    "text": s, "turn": turn, "role": role, "ts": time.time()}
            self.items.append(item); self._ngram_index.append(ng)
            kept.append(s); self.stats["kept"] += 1
        return kept, dropped

    def raw_text(self, max_items=None):
        its = self.items[-max_items:] if max_items else self.items
        return "\n".join(f"[T{i['turn']}|{i['role']}] {i['text']}" for i in its)

# ---------------- 2. 记忆整理 (LLM) ----------------

ORGANIZE_PROMPT = """你是记忆整理器。把下面"过滤后的原始记忆条目"整理成结构化的学生辅导记忆文档。

要求:
1. 分节组织: 【学生画像】【学习进展】【错题与薄弱点】【偏好与习惯】【近期事件】【待办与计划】(无内容的分节删掉)
2. 每条目尽量保留原始表述的关键细节(数字/名称/日期不得改动或编造), 并保留来源轮次标记 [T#]
3. 合并同义条目, 标注新信息取代旧信息(如 "之前认为X → 现已纠正为Y")
4. 条目按重要性排序, 重要的在前
5. 如果原始条目没有任何值得保留的信息, 只输出: NO-OP

当前已整理的记忆(需与其融合, 不是重新生成):
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的记忆文档, 不要输出任何解释。"""

# ---------------- 3. 记忆压缩 (LLM, Codex memory_summary 风格) ----------------

COMPRESS_PROMPT = """你是记忆压缩器。把下面的结构化记忆文档压缩成高密度摘要, 目标长度不超过原来的 {ratio}%:

压缩原则 (参考渐进式披露 progressive disclosure):
1. 电报式短语, 去掉所有客套和连接词; 用 "|" 分隔并列项, 用 "→" 表示因果/演变
2. 只保留高区分度信息: 能区别这个学生和其他学生的信息(具体数字/名称/错题/偏好)
3. 删除: 已被后续信息取代的旧条目、一次性闲聊、可由其他条目推导的冗余
4. 保留节标题但合并到一行内 (如 【画像】姓名小明|五年级|人教版); 关键条目保留来源轮次标记 [T#]
5. 如果文档已经足够紧凑(无法再压缩20%以上), 原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档, 不要输出任何解释。"""

def organize(store, call_llm):
    """整理层: 融合已有 organized + 新 raw。返回 (new_text, changed)。"""
    raw = store.raw_text()
    if not raw.strip():
        return store.organized, False
    out = call_llm(ORGANIZE_PROMPT.format(existing=store.organized or "(空)", raw=raw))
    if not out or "NO-OP" in out[:50]:
        return store.organized, False
    store.organized = out.strip()
    return store.organized, True

def compress(store, call_llm, ratio=50):
    """压缩层: 压缩 organized。返回 (new_text, changed)。"""
    doc = store.organized or store.raw_text()
    if not doc.strip():
        return store.compressed, False
    out = call_llm(COMPRESS_PROMPT.format(ratio=ratio, doc=doc))
    if not out:
        return store.compressed, False
    if out.startswith("[ALREADY-COMPACT]"):
        store.compressed = out.split("\n", 1)[1].strip() if "\n" in out else out
        return store.compressed, False
    store.compressed = out.strip()
    return store.compressed, True

# ---------------- 上下文组装 (默认: 回填记忆 + 新提问) ----------------

def default_memory_block(store):
    """优先级: 压缩 > 整理 > 原始保存。附时效与信任标注 (参考 Claude Code/Codex 召回怀疑原则)。"""
    last_turn = max((i["turn"] for i in store.items), default=0)
    trust = (f"\n(以上为截至第{last_turn}轮的历史记忆, 可能过时或有误; 与当前对话冲突时以当前对话为准; "
             f"记忆中没有的信息请明说不知道, 不要编造。)")
    if store.compressed:
        return "【长期记忆·压缩版】\n" + store.compressed + trust
    if store.organized:
        return "【长期记忆·整理版】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【长期记忆·原始保存】\n" + raw + trust) if raw else ""
