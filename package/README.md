# 辅导记忆助手 (Tutor Memory Kit)

一个**开箱即用**的中小学个性化辅导对话脚本，内置 6 种记忆模式，专治"聊着聊着 AI 就忘了/记错了学生情况"的问题。

---

## 一、给非技术用户：3 步上手

1. **安装 Python**（官网 python.org，安装时勾选 "Add to PATH"）。
2. **打开 `tutor_memory.py`**（用记事本即可），在最上面【用户填写区】填 3 样东西：
   - `API_KEY`：你的接口密钥
   - `BASE_URL`：接口地址（已预填好，一般不用动）
   - `MODEL`：模型名（已测试可用：`mimo-v2.5` 或 `longcat-2.0`）
3. **双击运行**（或命令行 `python tutor_memory.py`），浏览器会自动打开对话页面。

右侧栏会实时显示 AI "记住了什么"，黑色字体的学生卡片就是它脑子里的全部记忆。

---

## 二、6 种记忆模式怎么选

改脚本头里的 `MODE = "..."` 即可：

| 模式 | 原理 | 特点 |
|---|---|---|
| `linear` | 把全部聊天记录塞给 AI | 基线对照组，轮数多了幻觉严重 |
| `window` | 只带最近几轮 | 最省 token，但忘得最快 |
| `summary` | 旧对话压缩成一段摘要 | 省 token，但摘要会漂移失真 |
| `psm` ⭐ | **结构化学生卡片**（档案/知识点掌握度/盲点），放在 system 区 | **推荐**。实测抗幻觉最好（见 `results/`） |
| `psm_tail` | 同上，但卡片贴在最末条消息前 | 位置对照组 |
| `psm_dag` | psm + 知识点前置关系图 | 能追盲点的"病根"（如"分数加减差 ← 最小公倍数没掌握"） |

> ⭐ 默认 `psm`：2026-09-02 在 mimo-v2.5 / longcat-2.0 上的实测结论——结构化卡片放 **system 区** 抗幻觉效果最好。详见 `results/` 与 `design/memory_schema.md`。

---

## 三、给开发者 / 其他 AI 智能体

### 架构一句话
LLM 只负责**抽取**和**回答**；记忆的合并、冲突解决、盲点推导、卡片编译全部是**纯 Python 确定性代码**——这是抗幻觉的核心：卡片里没有的信息，模型被明确告知"不知道"。

### 关键入口
- **改记忆怎么进上下文** → 重写 `build_context(user_msg)`（脚本里有醒目注释标注的可重写槽位，返回 OpenAI messages 列表即可）
- **改记忆结构** → `apply_updates()`（合并逻辑）+ `compile_card()`（卡片文案）
- **改抽取 schema** → `EXTRACT_PROMPT`
- **加学科知识图谱** → 脚本头 `KNOWLEDGE_DAG`（前置关系）和 `RESOURCE_LIB`（资源库）

### 数据流
```
用户消息 → build_context() → LLM 回答
              ↓ 答完
   update_memory(): LLM 抽取 JSON → apply_updates() 合并
              → memory_state.json (落盘, 重启不丢)
```

### HTTP 接口（想接自己的前端）
- `POST /chat` body `{"message": "..."}` → `{"reply": "..."}`
- `GET /state` → 当前记忆状态（纯文本）

### 状态持久化
`memory_state.json` 与脚本同目录，删掉即"失忆重来"。

---

## 四、目录说明

| 位置 | 内容 |
|---|---|
| `package/tutor_memory.py` | 交付脚本（本 README 同目录） |
| `design/memory_schema.md` | 记忆方案设计文档 |
| `tests/testbed.py` | 自动化对比测试床（模拟学生 + 幻觉探针） |
| `results/` | 各模式实测数据 |
| `papers/` | 顶会文献调研笔记 |

## 五、常见问题

- **抽取失败怎么办？** 脚本会打印警告并跳过本轮，不会崩溃；推理型模型（mimo/longcat）需要较大 max_tokens，已内置。
- **能换学科吗？** 能。改 `TEACHER_PERSONA`、`KNOWLEDGE_DAG`、`RESOURCE_LIB` 三处即可。
- **多人同时用？** 当前为单会话演示版；多人部署请为每个学生建独立 `memory_state.json`。
