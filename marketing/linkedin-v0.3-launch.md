# LinkedIn Launch Plan: wisdomGraph 0.3.0

## Preflight before posting

- Confirm PyPI installer endpoints show `wisdomgraph 0.3.0` as latest. Verified on May 25, 2026 via `pip index`, PyPI JSON, and the PyPI Simple API.
- Confirm the GitHub README includes the Codex setup section.
- Pin the launch post for 7 days.
- Put the GitHub link in the first comment if you want maximum feed reach, or in the post body if install friction matters more than reach.

Primary link:
https://github.com/cklam12345/wisdomGraph

Install:

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
wisdom mcp-install --host codex
```

## Positioning

Core claim:
AI coding agents should not start every session with amnesia. wisdomGraph gives Claude Code, Codex, OpenClaw, and MCP hosts a persistent Neo4j-backed memory that compounds across projects and sessions.

What changed in 0.3.0:

- Codex MCP support.
- `wisdom quickstart` for first-time setup.
- Shared graph memory across MCP hosts.
- Expanded MCP tool surface for ingesting, remembering, learning, querying, reflecting, and reporting.
- Better local backend path through managed DozerDB/Neo4j.

Audience:

- AI engineers building agent workflows.
- Developers using Claude Code, Codex, or MCP.
- GraphRAG and knowledge-graph practitioners.
- Technical founders who want agent memory across projects.
- Neo4j users looking for AI-native use cases.

## Main Launch Post

I just released wisdomGraph 0.3.0.

The short version:

AI coding agents should not start every session with amnesia.

wisdomGraph gives Claude Code, Codex, OpenClaw, and any MCP host a persistent Neo4j-backed memory that compounds across projects and sessions.

Most agent memory systems are either:

- a summary file
- a vector store
- a one-off project graph
- context that disappears when the session ends

wisdomGraph takes a different route.

It stores memory as a living DIKW graph:

Knowledge -> Experience -> Insight -> Wisdom

Every run merges into Neo4j. The graph does not reset. Facts become patterns. Patterns become insights. Insights become wisdom.

Version 0.3.0 adds Codex MCP support, so Codex can now use the same persistent graph memory as Claude Code.

That means your agent can:

- ingest a codebase, note, paper, URL, or conversation
- remember decisions and lessons learned
- query prior project experience
- trace why a principle exists
- reflect across projects to promote repeated patterns into higher-level wisdom
- reuse the same memory graph across tools

Setup is now:

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
wisdom mcp-install --host codex
```

Then start a new Codex session and the MCP tools are available.

I built this because I do not think the future of agent memory is just bigger context windows.

Bigger context lets an agent read more.

Persistent graph memory lets an agent accumulate experience.

GitHub:
https://github.com/cklam12345/wisdomGraph

If you are building with Claude Code, Codex, MCP, Neo4j, GraphRAG, or agent memory, I would love feedback on the model and the 0.3.0 setup path.

## Shorter Post

wisdomGraph 0.3.0 is out.

The main addition: Codex MCP support.

wisdomGraph gives AI coding agents persistent Neo4j-backed memory across sessions and projects.

Instead of treating memory as a summary file or vector store, it uses a DIKW graph:

Knowledge -> Experience -> Insight -> Wisdom

Every run merges into the graph. The graph compounds.

Claude Code, Codex, OpenClaw, and MCP hosts can now use the same persistent memory layer.

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
wisdom mcp-install --host codex
```

GitHub:
https://github.com/cklam12345/wisdomGraph

I am looking for builders willing to try it on real projects and tell me where the memory model breaks.

## Technical Founder Version

I released wisdomGraph 0.3.0.

It is an open-source memory layer for AI coding agents.

The premise is simple: agents should accumulate experience across projects instead of starting from zero every session.

wisdomGraph stores agent memory in Neo4j as a DIKW hierarchy:

Knowledge -> Experience -> Insight -> Wisdom

Version 0.3.0 adds Codex MCP support, which means Claude Code and Codex can now share the same persistent graph memory.

This is useful when you want an agent to remember:

- architecture decisions
- debugging lessons
- recurring project patterns
- source-grounded rationale
- contradictions between old and new assumptions

It is not trying to be a chatbot memory toy. It is infrastructure for compounding agent work.

GitHub:
https://github.com/cklam12345/wisdomGraph

## DM Template: Warm Technical Contact

Hey [Name], I just released wisdomGraph 0.3.0 and thought of you because you have been working around [agents / MCP / Neo4j / coding assistants].

It gives Claude Code, Codex, and MCP hosts persistent Neo4j-backed memory across sessions and projects. The new release adds Codex MCP support.

Would value your technical read on whether the DIKW graph model makes sense for real agent workflows:
https://github.com/cklam12345/wisdomGraph

No pressure, just wanted to put it on your radar.

## DM Template: Potential Early User

Hey [Name], I released wisdomGraph 0.3.0.

It is a persistent memory layer for AI coding agents: Claude Code, Codex, OpenClaw, and MCP hosts can store and query a Neo4j-backed graph across sessions.

The part I think may be relevant to you: it is built for real project history, not just chat summaries.

If you try it on one repo, I would be grateful for blunt feedback:
https://github.com/cklam12345/wisdomGraph

## DM Template: Neo4j / Graph Person

Hey [Name], I just shipped wisdomGraph 0.3.0.

It uses Neo4j as a persistent cognition layer for AI coding agents, with memory organized as Knowledge -> Experience -> Insight -> Wisdom.

0.3.0 adds Codex MCP support, so the same graph can be used across agent hosts.

I would value your graph-native critique:
https://github.com/cklam12345/wisdomGraph

## First Comment

The repo is here:
https://github.com/cklam12345/wisdomGraph

Best first test:

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
wisdom mcp-install --host codex
```

I am especially looking for feedback from people using Claude Code, Codex, MCP, Neo4j, or GraphRAG in real workflows.

## Replies To Expected Comments

What is different from vector memory?

Vector memory retrieves semantically similar chunks. wisdomGraph stores typed relationships between facts, experiences, insights, and principles, then traverses that graph. The goal is not just recall. It is accumulated reasoning with provenance.

Does this replace RAG?

No. It is closer to a persistent reasoning substrate for an agent. You can still use RAG for document retrieval. wisdomGraph is for compounding project memory, lessons, decisions, and cross-project patterns.

Why Neo4j?

The relationships are the product. Cypher traversal, provenance paths, contradiction edges, and promotion through DIKW tiers are central to the model.

Is it only for Claude?

No. 0.3.0 adds Codex MCP support, and the MCP server can be used by other MCP hosts.

## 7-Day Sequence

Day 1: Launch post.

Angle: 0.3.0 is out, Codex MCP support, persistent graph memory for agents.

Optional community version:
Use `marketing/linkedin-wisdom-learn-community-post.md` with `marketing/wisdomLearn.png` to show wisdomGraph recording a real release-verification failure as agent memory.

Day 2: Technical diagram post.

Angle: Why DIKW instead of flat memory.

Post hook:
"Most AI memory systems store facts. Experts store relationships between facts, outcomes, patterns, and principles."

Day 3: Demo clip or screenshot.

Angle: Codex using `wisdom_report`, `wisdom_query`, or `wisdom_learn`.

Post hook:
"Here is Codex querying memory it did not have in its context window."

Day 4: Founder story.

Angle: Why bigger context windows are not enough.

Post hook:
"Bigger context lets an agent read more. It does not make the agent accumulate experience."

Day 5: Neo4j angle.

Angle: The graph database is the intelligence layer.

Post hook:
"For agent memory, the edge is often more important than the node."

Day 6: Open-source contributor ask.

Angle: Ask for worked examples.

Post hook:
"The highest-trust contribution to wisdomGraph is not code. It is a worked example from a real project."

Day 7: Results and feedback post.

Angle: Share early feedback, common objections, and what is next.

Post hook:
"After releasing wisdomGraph 0.3.0, the most useful feedback has been about where agent memory should stop."

## Targeted Outreach Buckets

- 50 people building with Claude Code or Codex.
- 50 MCP builders.
- 30 Neo4j or graph database practitioners.
- 30 GraphRAG / knowledge graph people.
- 25 AI engineering founders.
- 25 developer tools maintainers.

Send no more than 20-30 DMs per day. Prioritize people who have already engaged with your agent, graph, or MCP posts.

## Metrics To Track

- Profile views.
- GitHub stars.
- GitHub issues opened.
- PyPI downloads after 0.3.0 is visible.
- Replies from credible builders.
- Number of people who complete `wisdom quickstart`.
- Number of worked examples submitted.
