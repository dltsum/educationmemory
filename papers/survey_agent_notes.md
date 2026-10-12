# 顶会/主流文献调研: 结构化记忆 × 教学智能体记忆

> 调研日期 2026-09-02 | 调研方式: WebSearch/WebFetch + 先验知识交叉核对
> (注: 原定子 agent 调研因网关 504 中断, 本笔记由主 agent 重写; venue 信息如有不确定已标注)

## Part A: 通用结构化记忆系统

### A1. MemGPT / Letta (2023, arXiv; Letta 后续产品化)
- 核心: 把 LLM 上下文当"内存", 借鉴操作系统的分页思想, 主上下文(main context)+外部归档存储, 模型通过函数调用自主换入换出。
- 记忆结构: 分层(核心记忆块 / 召回存储 / 归档存储), 自编辑。
- 借鉴: "记忆即资源管理"思想; 但对弱模型而言让模型自己管理分页不可靠 → 本项目把管理逻辑全部代码化。

### A2. MemoryBank (AAAI 2024, Zhong et al.)
- 核心: 长程对话记忆 + Ebbinghaus 遗忘曲线; 每日对话蒸馏为摘要, 按时间衰减检索权重; 含用户画像(personality)持续更新。
- 借鉴: 遗忘曲线、画像槽位。本项目 L1 画像槽位 + 遗忘标注直接继承。

### A3. A-MEM (Agentic Memory, 2025, NeurIPS 2025 投稿, Xu et al.)
- 核心: Zettelkasten 卡片盒式原子笔记, 每条笔记含关键词/标签/上下文, 新笔记触发旧笔记动态链接与演化(memory evolution)。
- 借鉴: 原子化 + 链接演化; 但链接演化依赖 LLM 判断, 弱模型不稳 → 本项目用固定知识点 DAG 替代自由链接。

### A4. Mem0 / Mem0g (2025, Chhikara et al., arXiv 2504.19413)
- 核心: 两阶段 pipeline(抽取→更新: ADD/UPDATE/DELETE/NOOP), 生产级; Mem0g 加图存储(实体-关系三元组)。
- 关键数据: 相比全上下文, p95 延迟降 91%, token 成本降 90%+, LoCoMo 上准确率优于全上下文基线。
- 借鉴: ①ADD/UPDATE/RETRACT 操作集(本项目 v0.1 直接采用); ②成本论证——在"答得一样对"时, 结构化记忆赢在成本与可审计。

### A5. Zep / Graphiti (2025, 产品+论文)
- 核心: 时序知识图谱, 分 episodic(原始事件)/semantic(实体事实)/community(群体摘要)三层, 事实带 t_valid/t_invalid 时间区间, 支持事实失效(retraction)。
- 借鉴: 事实时效标注; 中小学场景可对应"已纠正的旧错误"。

### A6. HippoRAG / HippoRAG 2 (NeurIPS 2024 / ICML 2025)
- 核心: 海马体索引理论, KG + Personalized PageRank 做联想检索; 强项是多跳问答。
- 借鉴: 图上的扩散激活检索; 中小学课标前置 DAG 可做简化版扩散(盲点→前置根因)。

### A7. MemoryOS / MemOS (2025)
- 核心: 操作系统式三级存储(短/中/长期), 热冷数据迁移; MemOS 提出 MemCube 标准化记忆单元与调度。
- 借鉴: 分层+迁移策略; 本项目按"教学流程"(事件→事实→认知→计划)分层而非按热度。

### A8. LongMem (NeurIPS 2023)
- 核心: 解耦记忆网络, 冻结主干+残差侧网络缓存历史 KV。
- 借鉴: 参数化记忆路线——需要训练, 本项目 API-only 不可行, 仅作路线对照。

### A9. CoALA (2023, Princeton, 认知架构综述)
- 核心: 把智能体记忆分为工作记忆/情景记忆/语义记忆/程序记忆, 提供设计词汇表。
- 借鉴: 术语框架; 教学场景 = 情景(事件日志)+语义(学生画像/知识点)+程序(教学策略模板)。

### A10. Agent Workflow Memory (ICML 2025)
- 核心: 从历史轨迹归纳可复用 workflow, 注入后续任务。
- 借鉴: 教学场景的"讲解套路"可归纳为 workflow 记忆(讲分数→先通分→再算), 本项目暂未实现, 列入 v0.3 候选。

### A11. 安全综述 (arXiv 2604.16548, 2026)
- 核心: 长期记忆的投毒/篡改/隐私风险; 指出现有系统普遍缺版本化、回滚、写入门控、审计。
- 借鉴: 本项目每条记忆强制 evidence_turn_ids + 槽位版本历史(部分实现)。

## Part B: 教育智能体的学生记忆

### B1. Agent4Edu (AAAI 2025)
- 核心: 学习者模拟框架, 三模块: Learner Profile(IRT 能力值) / Memory(事实/短期/长期 + Ebbinghaus 遗忘) / Action(按检索到的记忆生成应答)。用于生成合成学习者数据训练 CAT/推荐算法。
- 借鉴: ①画像-记忆-行动三段式与本项目 L1/L2/L3 同构; ②遗忘建模用于"当前保持率"而非历史表现。

### B2. TASA (arXiv 2511.15163, 2025)
- 核心: 因材施教的数学辅导: persona 画像 + 事件记忆(最近解题 episodes) + 时间衰减模型动态调整熟练度估计, 再生成教学。
- 借鉴: "熟练度估计随时间衰减后再用于教学决策" —— 本项目卡片上的"3天前学过, 可能已遗忘"标注同源。

### B3. EduAgent (Xu et al., 2024)
- 核心: 四种结构化认知记忆模式: 凝视→生理记忆, 操作→运动记忆, 认知状态→认知记忆, 课后评估→知识记忆。
- 借鉴: 多模态记忆通道; 文本对话场景只用得上"认知记忆+知识记忆"。

### B4. GenAL (Lv et al., 2025)
- 核心: 用外部工具(代码/搜索)构建学生综合画像, 动态布置分层任务, 动态更新记忆。
- 借鉴: 画像驱动的任务分层。

### B5. Mem0 教学落地指南 (mem0.ai blog)
- 核心: user_id 按学生隔离, agent_id 按学科隔离, 语义检索记忆注入 system prompt。
- 借鉴: 多学生/多学科部署的 scoping 方案。

### B6. LLM Agents for Education 综述 (OpenReview)
- 核心: 学生支持 agent = 记忆+工具+规划; 结构化 student profile 是自适应学习/知识追踪/纠错的基础设施。

## Part C: 记忆幻觉与评测基准

### C1. LoCoMo (ACL 2024)
- 跨月多会话长对话记忆基准; 发现 RAG 摘要随对话增长性能显著退化; 全上下文在长对话上并非最优(噪声稀释)。

### C2. LongMemEval (ICLR 2025)
- 500 道精排题测 5 种记忆能力(信息抽取/多会话推理/时序/知识更新/ abstention); 发现主流助手在 abstention(不该答时不答)上最差——正是幻觉探针对应的能力。

### C3. 错误级联文献 (TeamLLM/M-CALLM 2026 等)
- 多轮模拟中一个错误记忆会在后续窗口级联放大(半衰期≤2窗口) → 线性叠加的隐性成本。

### C4. 工程实证 (Mem0/Zep 博客 + GitHub issues)
- 生产环境长会话线性叠加 → context overflow、token 成本爆炸、检索质量下降; 滑动窗口+检索的记忆(最近4轮+8条检索)在 LoCoMo 上以远低 token 匹配全量转录。

## Part D: 对本项目的 10 条具体启示

1. **管理代码化**: 弱模型不可靠地自我管理记忆(MemGPT 式自编辑需要强模型), 合并/去重/冲突/衰减必须确定性代码完成。
2. **操作集最小化**: ADD/UPDATE/RETRACT 三操作足够(Mem0 验证), 配合 JSON schema 约束输出。
3. **来源必附**: 每条记忆带 evidence_turn_id, 支持审计/回滚, 也阻断无来源幻觉入库(安全综述 D 缺口)。
4. **分层按"流程"而非"热度"**: 事件→事实→认知→教学计划, 每层只放该层粒度, 注入时只带编译后的卡片。
5. **遗忘要显示**: Ebbinghaus 衰减标注(MemoryBank/TASA)让"可能忘了"成为显式信息而非静默错误。
6. **知识点用固定本体**: 自由文本 KC 名导致粒度漂移(本项目实测), 固定列表+前置 DAG(简化 HippoRAG)。
7. **abstention 是关键指标**: LongMemEval 结论——弱模型最弱的是"该说不知道时说不知道", 卡片上必须显式写"卡片外信息禁止假设"。
8. **成本是核心卖点**: 当准确率打平时(Mem0 实证), 结构化记忆赢在 token 成本/延迟/可审计/可跨会话。
9. **错误级联防御**: 检索错误会级联, 所以抽取失败要显式跳过+日志(规则12), 不可带病入库。
10. **跨会话才是真优势场景**: 30 轮内线性不输(本项目实测), 结构化记忆的决定性场景是多天跨会话连续辅导。

## 参考链接
- Mem0: https://arxiv.org/html/2504.19413v1
- Mem0 教学指南: https://mem0.ai/blog/build-a-personalized-ai-tutor-with-persistent-memory
- Mem0 grounded memory: https://mem0.ai/blog/reducing-hallucinations-llms-with-grounded-memory
- Zep: https://www.getzep.com/ai-agents/reducing-llm-hallucinations/
- 记忆安全综述: https://arxiv.org/html/2604.16548v1
- 统一表征-管理综述: https://www.preprints.org/manuscript/202603.0359
- awesome-agentic-memory: https://github.com/Anandesh-Sharma/awesome-agentic-memory
- Agent4Edu: https://ojs.aaai.org/index.php/AAAI/article/view/34565/36720
- TASA: https://arxiv.org/html/2511.15163v1
- 教育 agent 综述: https://openreview.net/pdf?id=pO0x7tNTyP
- 短程记忆管理(工具调用): https://arxiv.org/html/2507.21428v1
