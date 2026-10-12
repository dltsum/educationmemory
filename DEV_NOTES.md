# DEV_NOTES — 实验过程记录 (持续更新)

## 2026-09-02

### API 事实 (opencode go)
- endpoint `https://opencode.ai/zen/go/v1/chat/completions`, OpenAI 兼容
- mimo-v2.5 / longcat-2.0 均为 reasoning 模型: `reasoning_content` 独立字段
- **坑**: max_tokens 过小(≤1200)时 reasoning 吃光预算, content 返回空串 → 抽取器必须 ≥4000
- 偶发 500, 重试机制有效

### v1 评测 (24轮, 7事实+2陷阱) — 结论: 难度不足
| 模型 | linear | psm |
|---|---|---|
| mimo-v2.5 | recall 1.0 / halluc 0 | recall 1.0 / halluc 0 |
| longcat-2.0 | recall 1.0 / halluc 0 | (运行中) |

- 24 轮短对话不足以压垮线性模式 → 设计 v2 压测 (30轮, 10轮闲聊干扰, 相似事实 82分/95分, 双考试日期, 4陷阱)
- 规则12 如实记录: v1 未能复现"线性幻觉严重", 可能的解释: (a)探针太简单 (b)reasoning 模型长上下文能力尚可 (c)需更长对话+相似干扰

### PSM 状态质量人工抽查 (mimo, v1)
- ✓ profile/notes 抽取准确, 无虚构
- ✗ 抽取保真度问题: 第18轮学生"先加后乘"错误被判 correct → `分数混合运算 mastery 0.625 errors 0`
  → v0.2 改进: 抽取 prompt 要求引用学生原话作 evidence; 老师确认正确才算 correct
- blind_spots 判定生效过慢 (v1 结束为空, 因后续答对把 mastery 拉过 0.6) → 合理, 但 errors 计数应保留在卡片上

### 交付包
- package/tutor_memory.py: 6 模式 + build_context 可重写槽位 + 零依赖 Web UI + memory_state.json 持久化
- 离线单测: DAG 根因追踪 ✓ (分数加减盲点 → 最小公倍数/分数意义 前置)

## 2026-09-03 (v2 三层记忆重构)

### 新需求 (用户)
- 三层机制: 保存(本地无API, 过滤式非槽位式, 基础=去重) / 整理(LLM结构化) / 压缩(参考记忆.docx, Codex渐进披露)
- 真实数据集构造多轮QA + 长学生信息填充
- 前端: API key填写 + 自定义上下文方法导入 + 实时记忆面板 + 整理/压缩按钮动态UI

### 参考文档 记忆.docx 要点
- Claude Code: MEMORY.md索引+条目文件; fork session 事后抽取; Dream 异步整合(默认未开); 召回保持怀疑, >1天记忆附时效提醒
- Codex: Phase1 mini模型并行抽取rollout → Phase2 整合 progressive disclosure (memory_summary.md 常驻+dense+navigational); NO-OP门控("没有值得记的就不记"); 高信号=稳定偏好/流程知识/任务地图/环境证据
- 番外教训: 记忆堆积→可塑性丧失(模型变"懒惰") → 压缩的必要性实证
- 核心原则: "Memory设计重点在于不记什么和不信什么"

### 数据源
- MathDial (HF eth-nlped/mathdial): 100条已下载, 含 student_profile/student_incorrect_solution/conversation

### 事故: 403 限流 (第一次 v2 测试全废)
- 并发2测试床+server E2E → opencode go 403 风暴; organized/compressed 全空, recall 0 无效
- 处置: 删除污染结果; call_llm 改 6 次指数退避(≤60s); 串行重跑
- 教训: 该 key 并发预算小, 任何时刻最多 1 个跑批进程 + 前台低频

### v2 修复记录
- _ACK 整句正则 → _is_ack 子句级判定 ("好的，谢谢！" 复合型应答原来漏删)
- server _body 兼容 GBK (curl 中文)

### 文档对照审计 (v2/AUDIT.md)
- 修复4项: 敏感信息脱敏(中文边界\b失效→数字环视) / 记忆块时效信任标注(best_block) / 整理压缩保留[T#]来源 / ACK词表定位说明
- 有意不采纳: RAG召回(单学生量小) / Dream异步(用户指定手动) / 用户编辑入口
- 回归: 脱敏3/3, E2E整理压缩带[T#]通过, 服务运行中 :8766
