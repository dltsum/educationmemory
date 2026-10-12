# -*- coding: utf-8 -*-
"""
记忆风格流派 (依据 记忆.docx 调研材料: Claude Code / Codex / MemGPT 等主流 Agent 记忆设计)
每种风格 = {整理提示词, 压缩提示词, 上下文块构造函数}
  three_layer : 本系统默认三层 (保存过滤→分节整理→电报压缩)
  claude_code : Claude Code 风格 —— 索引+条目双层, 召回怀疑(记忆可能过时/有误需标注), 时效提醒
  codex       : Codex 风格 —— memory_summary.md 渐进披露: dense(高密度)+navigational(可定位)+discriminative(高区分)
  memgpt      : MemGPT 风格 —— 核心记忆(常驻画像小块)+归档记忆(附录摘要), 类 self-editing 分层
"""
import memory_core as mc

# ---------------- Claude Code 风格 ----------------
CC_ORGANIZE = """你是记忆整理器 (Claude Code 风格)。把"过滤后的原始记忆条目"整理为「索引+条目」双层记忆:

格式:
## 索引
- [画像] 学生基本情况一行摘要
- [进展] 学习进展一行摘要
- [错题] 薄弱点一行摘要
- [偏好] 偏好习惯一行摘要
- [事件] 近期事件一行摘要
## 条目
### [画像]
- 具体条目, 保留数字/名称/日期原文, 附来源轮次 [T#]
### [进展]
...(每个索引项对应一个条目小节; 无内容的小节删掉)

要求:
1. 索引必须能独立回答"大概", 条目回答"具体"; 合并同义条目, 标注 "之前X→现已纠正为Y"
2. 与已有记忆融合(不是重新生成); 没有值得保留的信息时只输出: NO-OP

当前已整理的记忆:
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的记忆文档。"""

CC_COMPRESS = """你是记忆压缩器 (Claude Code 风格)。把下面的记忆文档压缩为原来的 {ratio}% 以内:
1. 索引行全部保留并进一步凝练; 条目只保留高区分度条目 (具体数字/名称/错题)
2. 每条保留来源轮次 [T#]; 已过时条目直接删除
3. 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def cc_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = (f"\n(记忆使用守则: 以上记忆截至第{last}轮, 可能过时、遗漏或记错; "
             f"与当前对话冲突时以当前对话为准; 记忆中没有的信息请明确说'我的记录里没有', 不要凭印象编造。)")
    if store.compressed:
        return "【记忆索引·压缩版】\n" + store.compressed + trust
    if store.organized:
        return "【记忆索引+条目】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【记忆条目·未整理】\n" + raw + trust) if raw else ""

# ---------------- Codex 风格 ----------------
CX_ORGANIZE = """你是记忆摘要器 (Codex memory_summary 风格)。把"过滤后的原始记忆条目"写为高密度记忆摘要:

原则 (progressive disclosure 渐进披露):
1. dense: 电报式短语, 无客套无连接词, 信息密度最大化
2. navigational: 分节+关键词前置, 让未来的你能快速定位 (节: 学生/学业/错题/偏好/事件/待办)
3. discriminative: 只保留能区分这个学生与其他学生的信息 (具体数字/名称/日期/错因), 泛化常识删除
4. 关键条目附来源轮次 [T#]; 没有值得保留的信息时只输出: NO-OP

当前已有摘要(需融合):
{existing}

过滤后的原始记忆条目:
{raw}

只输出摘要文档。"""

CX_COMPRESS = """你是记忆压缩器 (Codex 风格)。把下面的摘要压缩到 {ratio}% 以内:
1. "|" 分隔并列, "→" 表因果/演变; 节标题并入行内
2. 删除: 被取代的旧信息、一次性闲聊、可推导的冗余; 关键条目保留 [T#]
3. 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def cx_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = f"\n(memory_summary 截至第{last}轮; 依据记忆作答时若不确定, 声明可能已过时。)"
    if store.compressed:
        return "## memory_summary.md (compressed)\n" + store.compressed + trust
    if store.organized:
        return "## memory_summary.md\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("## raw notes\n" + raw + trust) if raw else ""

# ---------------- MemGPT 风格 ----------------
MG_ORGANIZE = """你是记忆管理器 (MemGPT 风格)。把"过滤后的原始记忆条目"整合为两层记忆:

## 核心记忆 (core memory, 常驻上下文, 必须极简)
### 学生画像
- 最多6条: 身份/性格类型/最薄弱知识点/最强偏好/当前目标, 每条≤20字
### 教学策略
- 最多3条: 根据性格与图谱得出的讲解策略
## 归档记忆 (archival memory, 附录)
- 其余全部具体信息: 图谱数值/提问统计/错题记录/事件, 保留数字原文与来源轮次 [T#]

要求: 核心记忆超出条数上限时, 把相对不重要的条目降级到归档; 与已有记忆融合; 没有值得保留的信息时只输出: NO-OP

当前已有记忆:
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的记忆文档。"""

MG_COMPRESS = """你是记忆压缩器 (MemGPT 风格)。把下面的记忆文档压缩到 {ratio}% 以内:
1. 核心记忆条数不变但每条再凝练; 归档记忆删除低区分度条目
2. 关键条目保留 [T#]; 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def mg_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = f"\n(核心记忆常驻, 归档记忆为附录; 截至第{last}轮, 记忆没有的信息请明说不知道。)"
    if store.compressed:
        return "【核心+归档记忆·压缩版】\n" + store.compressed + trust
    if store.organized:
        return "【核心+归档记忆】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【归档记忆·未整理】\n" + raw + trust) if raw else ""

# ---------------- Generative Agents 风格 (Park et al. 2023) ----------------
GA_ORGANIZE = """你是记忆流整理器 (Generative Agents 风格, Park et al. 2023)。把"过滤后的原始记忆条目"整理为「观察→反思」双层记忆流:

格式:
## 观察 (observations, 底层事实)
- 具体事件/发言, 保留数字/名称/日期原文, 附来源轮次 [T#]
## 反思 (reflections, 高层洞见)
- 从观察归纳出的上位结论 (如"学生在分数运算上的困难根源于通分不熟练"), 每条反思末尾标注其证据观察 [T#→T#]

生成规则:
1. 只有证据足够(≥2条相关观察)时才生成一条反思; 证据不足只保留观察
2. 反思必须能被观察支撑, 禁止过度推测; 与已有记忆融合
3. 没有值得保留的信息时只输出: NO-OP

当前已有记忆:
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的记忆文档。"""

GA_COMPRESS = """你是记忆压缩器 (Generative Agents 风格)。把下面的记忆流压缩到 {ratio}% 以内:
1. 反思层全保留(它们是高价值洞见), 观察层只保留支撑反思的关键证据和最新事件
2. 每条保留 [T#]; 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def ga_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = f"\n(反思是对截至第{last}轮观察的归纳, 可能有偏差; 与当前对话冲突时以当前对话为准。)"
    if store.compressed:
        return "【记忆流·反思+观察 (压缩版)】\n" + store.compressed + trust
    if store.organized:
        return "【记忆流·反思+观察】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【观察流·未反思】\n" + raw + trust) if raw else ""

# ---------------- MemoryBank 风格 (Zhong et al. 2023) ----------------
MB_ORGANIZE = """你是记忆库管理器 (MemoryBank 风格, Zhong et al. 2023)。把"过滤后的原始记忆条目"整理为带显著性评分的记忆库:

格式:
## 个性画像 (持续更新)
- 学生特质/偏好/目标, 每条附来源 [T#]
## 事件记忆 (按显著性排序)
- [显著性:高/中/低] 事件描述 (保留数字/名称/日期), 附 [T#]

评分规则:
1. 显著性=该信息对长期辅导的价值: 错因模式/性格特质/目标=高; 单次提问内容=中; 闲聊=低
2. 模拟艾宾浩斯遗忘: 旧的低显著性条目直接淘汰; 高显著性条目即使旧也保留并标注"长期记忆"
3. 与已有记忆融合; 没有值得保留的信息时只输出: NO-OP

当前已有记忆:
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的记忆文档。"""

MB_COMPRESS = """你是记忆压缩器 (MemoryBank 风格)。把下面的记忆库压缩到 {ratio}% 以内:
1. 先淘汰 [显著性:低] 的旧条目; 高显著性条目优先保留; 画像层只保留区分度最高的特质
2. 每条保留 [T#] 与显著性标注; 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def mb_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = f"\n(记忆库截至第{last}轮, 低显著性旧记忆已被遗忘机制淘汰; 记忆缺失的信息请明说不知道。)"
    if store.compressed:
        return "【记忆库·画像+事件 (压缩版)】\n" + store.compressed + trust
    if store.organized:
        return "【记忆库·画像+事件】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【事件流·未入库】\n" + raw + trust) if raw else ""

# ---------------- A-MEM 风格 (Agentic Memory, Xu et al. 2025) ----------------
AM_ORGANIZE = """你是卡片盒记忆管理器 (A-MEM 风格, Agentic Memory 2025, 借鉴 Zettelkasten)。把"过滤后的原始记忆条目"整理为互相链接的记忆卡片网络:

每张卡片格式:
### 卡片 #[序号] | 关键词1, 关键词2
- 内容: 一句凝练的事实 (保留数字/名称/日期), 附 [T#]
- 背景: 这条记忆的情境与意义 (为什么值得记)
- 链接: 与哪些已有卡片相关 → [#序号] (写明关系: 因果/同类/前置/对比)

规则:
1. 新条目优先生成新卡片并链接旧卡片; 同义内容更新旧卡片而非新建
2. 链接是核心: 薄弱知识点卡片应链接到其前置知识点与相关错题卡片
3. 与已有卡片网络融合; 没有值得保留的信息时只输出: NO-OP

当前已有卡片网络:
{existing}

过滤后的原始记忆条目:
{raw}

只输出整理后的卡片网络。"""

AM_COMPRESS = """你是记忆压缩器 (A-MEM 风格)。把下面的卡片网络压缩到 {ratio}% 以内:
1. 合并内容重叠的卡片(保留双方链接); 删除无链接的孤立低价值卡片
2. 卡片保留关键词/链接/[T#]; 已足够紧凑时原样返回并首行标注 [ALREADY-COMPACT]

待压缩文档:
{doc}

只输出压缩后的文档。"""

def am_block(store):
    last = max((i["turn"] for i in store.items), default=0)
    trust = f"\n(卡片网络截至第{last}轮; 回答时可沿卡片链接追溯相关信息; 网络中没有的信息请明说不知道。)"
    if store.compressed:
        return "【记忆卡片网络 (压缩版)】\n" + store.compressed + trust
    if store.organized:
        return "【记忆卡片网络】\n" + store.organized + trust
    raw = store.raw_text(max_items=60)
    return ("【未卡片化条目】\n" + raw + trust) if raw else ""

# ---------------- 注册表 ----------------
STYLES = {
    "三层记忆 (本系统默认)": {
        "organize": mc.ORGANIZE_PROMPT, "compress": mc.COMPRESS_PROMPT,
        "block": mc.default_memory_block,
        "desc": "保存过滤(本地)→分节整理→电报压缩; 整理/压缩各一次 LLM 调用"},
    "Claude Code 风格": {
        "organize": CC_ORGANIZE, "compress": CC_COMPRESS, "block": cc_block,
        "desc": "索引+条目双层; 召回怀疑与时效标注; 压缩保留索引行"},
    "Codex 风格": {
        "organize": CX_ORGANIZE, "compress": CX_COMPRESS, "block": cx_block,
        "desc": "memory_summary.md; dense+navigational+discriminative 渐进披露"},
    "MemGPT 风格": {
        "organize": MG_ORGANIZE, "compress": MG_COMPRESS, "block": mg_block,
        "desc": "核心记忆(常驻极简画像+策略)+归档记忆(附录详情)"},
    "Generative Agents 风格 (Park'23)": {
        "organize": GA_ORGANIZE, "compress": GA_COMPRESS, "block": ga_block,
        "desc": "观察→反思双层记忆流; 证据≥2条才生成反思, 反思必须可被观察支撑"},
    "MemoryBank 风格 (Zhong'23)": {
        "organize": MB_ORGANIZE, "compress": MB_COMPRESS, "block": mb_block,
        "desc": "画像+事件记忆库; 显著性评分+艾宾浩斯遗忘淘汰低价值旧记忆"},
    "A-MEM 风格 (Agentic Memory'25)": {
        "organize": AM_ORGANIZE, "compress": AM_COMPRESS, "block": am_block,
        "desc": "Zettelkasten 卡片网络: 关键词+背景+卡片间链接, 沿链追溯"},
}
DEFAULT_STYLE = "三层记忆 (本系统默认)"

def organize_with(store, call_llm, style):
    """按风格整理。返回 (new_text, changed)。"""
    raw = store.raw_text()
    if not raw.strip():
        return store.organized, False
    out = call_llm(STYLES[style]["organize"].format(existing=store.organized or "(空)", raw=raw))
    if not out or "NO-OP" in out[:50]:
        return store.organized, False
    store.organized = out.strip()
    return store.organized, True

def compress_with(store, call_llm, style, ratio=50):
    doc = store.organized or store.raw_text()
    if not doc.strip():
        return store.compressed, False
    out = call_llm(STYLES[style]["compress"].format(ratio=ratio, doc=doc))
    if not out:
        return store.compressed, False
    if out.startswith("[ALREADY-COMPACT]"):
        store.compressed = out.split("\n", 1)[1].strip() if "\n" in out else out
        return store.compressed, False
    store.compressed = out.strip()
    return store.compressed, True

def block_with(store, style):
    return STYLES[style]["block"](store)
