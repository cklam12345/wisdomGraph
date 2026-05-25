# LinkedIn Community Post: wisdomGraph Learning From Its Own Mistake

Image to attach:
`/home/human/Pictures/Screenshots/wisdomLearn.png`

Alt text:
Screenshot of a terminal and browser. The browser shows PyPI with `wisdomgraph 0.3.0` as the latest version. The terminal shows a user calling out an AI assistant for repeating a release-verification mistake, followed by the assistant attempting to record the failure as a `wisdom_learn` lesson in wisdomGraph.

## Main Post

This screenshot is probably the cleanest explanation of why I built wisdomGraph.

I had just released wisdomGraph 0.3.0.

I asked my coding agent to help with the launch.

It checked PyPI through a stale rendered page, concluded that `0.3.0` was not visible, and told me to delay the launch.

But I was looking at PyPI with my own eyes.

`wisdomgraph 0.3.0`

Latest version.

Right there.

So I called it out:

"you are obviously not using wisdomgraph as your memory to learn your mistake?"

And that is the product.

Not the mistake.

The recovery loop.

The agent turned the failure into a durable lesson:

For package release verification, do not rely on cached rendered web pages or search snippets alone. Check installer-facing endpoints such as `pip index`, PyPI JSON, and the Simple API before advising launch readiness.

That lesson is now in the graph.

Then wisdomGraph reflected on it and promoted it into a failure anti-pattern.

This is what I mean by persistent cognition for AI agents.

Not "memory" as a bigger context window.

Not "memory" as a summary file.

Memory as accumulated experience:

- what was tried
- what failed
- why it failed
- what should be avoided next time
- how that lesson connects to future decisions

The interesting part of agent memory is not perfect recall.

The interesting part is whether the system can become harder to fool by the same class of mistake.

wisdomGraph 0.3.0 is live now.

It works with Claude Code, Codex, OpenClaw, and MCP hosts.

GitHub:
https://github.com/cklam12345/wisdomGraph

PyPI:
https://pypi.org/project/wisdomgraph/

## Shorter Version

This screenshot is the product.

I asked my coding agent to help launch wisdomGraph 0.3.0.

It checked a stale PyPI page and incorrectly told me the release was not live.

I was looking at `wisdomgraph 0.3.0` on PyPI with my own eyes.

So I called it out:

"you are obviously not using wisdomgraph as your memory to learn your mistake?"

The agent then recorded the failure into wisdomGraph:

Do not verify package releases from cached rendered pages alone. Use `pip index`, PyPI JSON, and the Simple API before advising launch readiness.

That is the loop I care about.

Agents should not just make mistakes.

They should accumulate the lessons from them.

wisdomGraph 0.3.0 is live:
https://github.com/cklam12345/wisdomGraph

## First Comment

The release is here:
https://pypi.org/project/wisdomgraph/

Repo:
https://github.com/cklam12345/wisdomGraph

Best first test:

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
wisdom mcp-install --host codex
```

## Suggested Hook Variants

1. My AI agent made a launch mistake. Then it wrote the mistake into its own memory graph.
2. This is the difference between chatbot memory and agent experience.
3. The most important part of agent memory is not recall. It is not repeating the same class of failure.
4. A bigger context window would not have fixed this. A durable failure lesson might.

## Comment Replies

Is this staged?

No. The mistake was real: a cached rendered PyPI page disagreed with PyPI JSON, the Simple API, and `pip index`. The screenshot captures the moment I pushed the agent to store the lesson.

Why is this better than a note file?

A note file can store the text. wisdomGraph stores it as an Experience with outcome, confidence, project context, and promotion paths into anti-pattern Insights and Wisdom.

What changed in 0.3.0?

Codex MCP support, `wisdom quickstart`, broader MCP tools, and a smoother path for using one persistent Neo4j-backed graph across agent hosts.

