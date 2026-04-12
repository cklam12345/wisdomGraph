# wisdomGraph

[English](README.md) | [简体中文](README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/wisdomgraph)](https://pypi.org/project/wisdomgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Neo4j](https://img.shields.io/badge/Neo4j-native-008CC1?logo=neo4j)](https://neo4j.com)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-skill-blueviolet)](https://claude.ai/code)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-orange)](https://openclaw.ai)

> **graphify 给你快照。wisdomGraph 给你复利增长的记忆。**

在 Claude Code 或 OpenClaw 中输入 `/wisdom`。把你的代码库、笔记、论文、对话喂给它 —— 每次运行都会**合并**进一个活跃的 Neo4j 图谱。图谱不会重置，只会积累。事实变成模式，模式变成洞察，洞察变成智慧。

```
/wisdom .                      # 将当前项目吸收进智慧图谱
/wisdom ask "我所有项目中有哪些反复出现的模式？"
/wisdom reflect                # 启动 DIKW 晋升，形成智慧闭环
```

---

## 相较于 graphify 的质变

graphify 在其定位上做得很好：把一个文件夹变成知识图谱快照。跑一次，生成 `graph.json` 和 `GRAPH_REPORT.md`，读完，下次会话从头开始。

wisdomGraph 做的是根本不同的事。

| | graphify | wisdomGraph |
|---|---|---|
| **存储** | `graph.json` 文件（每个项目独立） | Neo4j（持久化，跨所有项目） |
| **节点类型** | 扁平（代码实体、概念） | DIKW 分层：知识 / 经验 / 洞察 / 智慧 |
| **每次运行** | 快照，覆盖写入 | MERGE —— 每次运行都在扩张图谱 |
| **查询方式** | 读取 GRAPH_REPORT.md | 运行时实时 Cypher 遍历 |
| **记忆** | 每次会话重置 | 跨会话、跨项目、跨月份积累 |
| **推理** | Leiden 社区检测（拓扑） | 图路径遍历 + DIKW 层次 |
| **反馈闭环** | 无 | 智慧 → 知识（神经可塑性） |
| **数据库** | 不需要 | Neo4j Aura（免费）或 DozerDB Docker |

这个差异不是量变，而是质变。graphify 把代码库压缩成可读报告；wisdomGraph 构建的是一套人工认识论 —— 能记忆、能关联、能成长。

---

## DIKW 金字塔，工程化落地

人类专家不是把事实平铺存储的，他们按层次组织经验：

```
智慧（Wisdom）   ← 从模式中提炼出的可执行原则
  ↑
洞察（Insight）  ← 从多次经验中发现的规律
  ↑
经验（Experience）← 有上下文的事件、决策与结果
  ↑
知识（Knowledge） ← 已验证的事实、文档行为、提取的结构
```

wisdomGraph 中每个节点都带有 `tier` 标签。图谱的拓扑结构**就是**认知架构本身。当你提问时，Cypher 沿层级向上遍历 —— 不是关键词匹配扁平文本，而是跨越亲历经验的推理。

反馈闭环至关重要：当某个智慧节点被查询并确认有效时，它会强化连接的知识节点。图谱在学习什么重要。

---

## 安装

**环境要求：** Python 3.10+ 以及以下之一：[Claude Code](https://claude.ai/code)、[OpenClaw](https://openclaw.ai)

**加上以下之一：** [Neo4j Aura 免费版](https://neo4j.com/cloud/platform/aura-graph-database/)（云端，无需安装）或 [DozerDB](https://dozerdb.org)（本地 Docker，含 APOC）

```bash
pip install wisdomgraph && wisdom install
```

### 方案 A — Neo4j Aura（零基础设施，推荐个人用户）

1. 在 [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura) 注册免费账号
2. 创建一个免费的 AuraDB 实例，复制连接 URI 和密码
3. 运行：

```bash
wisdom connect bolt+s://xxxxxxxx.databases.neo4j.io --user neo4j --password <你的密码>
```

免费额度：20 万节点，够用好几年。

### 方案 B — DozerDB 本地 Docker（完全掌控，含 APOC）

```bash
wisdom docker up        # 拉取 graphstack/dozerdb:5.26.3.0 并启动
wisdom connect bolt://localhost:7687 --user neo4j --password password
```

打开 [localhost:7474](http://localhost:7474) —— Neo4j Browser 是你俯瞰智慧图谱的可视化窗口。

---

## 平台支持

| 平台 | 安装命令 |
|------|---------|
| Claude Code (Linux/Mac) | `wisdom install` |
| Claude Code (Windows) | `wisdom install --platform windows` |
| OpenClaw | `wisdom install --platform claw` |

然后打开你的 AI 编程助手，输入：

```
/wisdom .
```

---

## 使用方式

```
/wisdom                              # 吸收当前目录
/wisdom ./raw                        # 吸收指定文件夹
/wisdom ./raw --mode deep            # 激进模式，提取更多 INFERRED 边
/wisdom ./raw --update               # 只重新吸收变更文件，MERGE 进图谱

/wisdom add https://arxiv.org/abs/1706.03762   # 吸收一篇论文
/wisdom add https://x.com/...                  # 吸收一条推文
/wisdom add https://...  --author "姓名"        # 标注来源作者

/wisdom ask "我所有项目中有哪些反复出现的模式？"
/wisdom ask "我对认证流程了解多少？"
/wisdom ask "从 attention 到 optimizer 的路径是什么？"
/wisdom ask "..." --tier wisdom      # 只遍历智慧层节点

/wisdom reflect                      # 运行 DIKW 晋升：知识→经验→洞察→智慧
/wisdom reflect --project ./raw      # 只对该语料库进行反思

/wisdom path "DigestAuth" "OAuth"    # 两个概念之间的最短路径
/wisdom explain "CausalSelfAttention"  # 某节点的完整 DIKW 上下文
/wisdom god-nodes                    # 所有项目中连接度最高的概念

/wisdom export --cypher              # 导出为 Cypher 语句
/wisdom export --json                # 导出 graph.json（与 graphify 兼容）
/wisdom export --obsidian            # 导出 Obsidian 知识库

/wisdom status                       # 各层节点统计
/wisdom purge --project ./raw        # 删除单个语料库的节点，不影响其他
```

---

## 智慧如何复利积累

**第 1 次运行** —— 吸收你的 auth 库：
```
知识：JWT、session token、cookie flags、PKCE flow
经验：（暂无 —— 只有一个来源）
```

**第 2 次运行** —— 吸收另一个项目的 auth：
```
知识：JWT、PKCE —— MERGE 去重，增加来源链接
经验：两个不同实现，检测到相同模式
洞察：JWT + PKCE 是你工作中收敛的模式
```

**第 3 次运行** —— `/wisdom reflect`：
```
智慧："API 用无状态 JWT，浏览器端用 PKCE flow。
       这个模式在 3 个项目中落地，从未出过问题。"
```

**第 4 次运行** —— `/wisdom ask "新服务的认证方案怎么定？"`：
```
遍历路径：知识 → 经验 → 洞察 → 智慧
返回结果：你自己经过实战验证的原则，根植于你真实的代码历史
```

这不是 RAG，不是摘要，而是图谱遍历你积累的经验，把**你自己的智慧还给你**。

---

## 图谱 Schema

```cypher
// DIKW 节点标签
(:Knowledge  {id, label, content, source_file, confidence, timestamp, project})
(:Experience {id, label, content, context, outcome, timestamp, project})
(:Insight    {id, label, content, pattern_strength, source_count, timestamp})
(:Wisdom     {id, label, principle, confidence, reinforcement_count, timestamp})

// 关系类型
(Knowledge)-[:GROUNDS]->(Experience)
(Experience)-[:REVEALS]->(Insight)
(Insight)-[:CRYSTALLIZES_INTO]->(Wisdom)
(Wisdom)-[:REINFORCES]->(Knowledge)           // 反馈闭环 —— 图谱在学习

(Knowledge)-[:SEMANTICALLY_SIMILAR_TO]->(Knowledge)
(Insight)-[:CONTRADICTS]->(Insight)           // 张力浮现，需要反思
(any)-[:SOURCED_FROM]->(Source {uri, author, ingested_at})
```

置信度沿图谱向上流动。8 个经验支撑的洞察比 2 个支撑的模式强度更高。智慧节点追踪 `reinforcement_count` —— 遍历确认该原则有效的次数。

---

## 你能得到什么

**跨项目神节点** —— 跨越*所有*项目和语料库的核心概念，而不仅是单个仓库的。

**矛盾检测** —— 两个洞察方向相反时，以 `CONTRADICTS` 边的形式浮现。图谱展示冲突，由你解决，形成更好的智慧。

**时间衰减** —— 节点带时间戳。长时间未被强化的旧知识会被标记。图谱优雅地老化，如同专家的记忆。

**完整溯源链** —— 每个节点关联到其 `Source`。`/wisdom explain "节点名"` 返回完整 DIKW 路径：事实 → 上下文 → 模式 → 原则。

---

## 部署方案对比

| | Aura 免费版 | DozerDB 本地 |
|---|---|---|
| **配置** | 3 步点击 + URI | 1 条 docker 命令 |
| **费用** | 免费（20 万节点） | 永久免费 |
| **APOC** | 可用 | 内置 |
| **数据位置** | Neo4j 云端 | 你自己的机器 |
| **可视化** | neo4j.com 控制台 | localhost:7474 |
| **适合** | 快速上手、个人用户 | 团队、离线、完全掌控 |

---

## 隐私说明

wisdomGraph 将文件内容发送给你的 AI 编程助手的底层模型 API 进行语义提取 —— Anthropic（Claude Code）或你所在平台使用的任何模型。代码文件通过 tree-sitter AST 在本地处理，不会发送到外部。所有图谱数据存储在*你的* Neo4j 实例中（Aura 或本地）。无遥测、无使用追踪、无任何形式的数据分析。

---

## 技术栈

Neo4j（Aura 或 DozerDB）+ tree-sitter + APOC。语义提取通过 Claude（Claude Code）或你平台的模型完成。图数据库就是智能层 —— 遍历、路径查找和社区检测通过 Neo4j GDS（图数据科学库）原生 Cypher 运行。

---

<details>
<summary>贡献指南</summary>

**工作示例**是最有说服力的贡献。在真实的多项目语料库上跑 `/wisdom`，让它反思几轮，记录涌现出哪些智慧节点、是否与你的直觉吻合。提交到 `worked/{slug}/`。

**Schema 提案** —— 如果你有捕捉当前 Schema 遗漏语义的关系类型，欢迎提 issue，附上 Cypher 模式和工作示例。

**DIKW 晋升启发式** —— 更好的知识→经验→洞察→智慧晋升提示词或规则。晋升逻辑是系统的核心。

详见 [ARCHITECTURE.md](ARCHITECTURE.md) 了解完整流水线设计、Cypher Schema 和如何扩展 DIKW 层次。

</details>
