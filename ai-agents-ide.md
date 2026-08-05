# AI Coding Agents for an Angular + Spring Boot + MySQL Team

**Prepared:** 6 August 2026
**Team profile:** 10 developers · Angular front end · Java Spring Boot REST APIs · MySQL · GitHub Team + Actions · Eclipse IDE · AWS EC2 + Tomcat · no defined work board

> **Pricing caution:** every vendor in this space changed its billing model between late 2025 and mid-2026, mostly moving from flat seats to credit/token metering. Treat all figures below as indicative and confirm on the vendor pricing page before committing budget. Assume real spend runs materially above the sticker price once agentic features are used daily.

---

## 1. The two constraints that shape your options

Before the tool list, two things about your setup narrow the field more than anything else.

### Eclipse is the binding constraint

Most of the 2026 agent ecosystem is built on VS Code or as a VS Code fork. The tools with genuine Eclipse support are a short list:

| Tool | Eclipse support |
|---|---|
| GitHub Copilot | Official first-party plugin on Eclipse Marketplace (plus the community `Copilot4Eclipse`) |
| Amazon Q Developer | Official Eclipse plugin — **but AWS has announced end of support for Q Developer IDE plugins on 30 April 2027** |
| Tabnine | Broadest legacy-IDE coverage in the market (Eclipse, VS Code, JetBrains, Vim, Emacs) |
| Claude Code / OpenAI Codex | No Eclipse plugin, but **terminal- and CLI-native**, so they run alongside Eclipse regardless of IDE |
| Cursor / Devin Desktop / Kiro / Antigravity | None — adopting these means leaving Eclipse |

This gives you three strategic paths:

1. **Stay in Eclipse** → Copilot for Eclipse, Tabnine, or a CLI agent running in a side terminal.
2. **Add a CLI/agent layer next to Eclipse** → Claude Code or Codex in Git Bash/WSL; the IDE keeps doing what it does, the agent does multi-file work. Lowest-disruption way to get real agentic capability.
3. **Migrate the front-end developers to VS Code** → Angular/TypeScript tooling in VS Code is already better than Eclipse's, and it unlocks the entire agent ecosystem. A split-IDE team (Angular devs in VS Code, Java devs in Eclipse) is a very common and workable arrangement.

### Your undefined work board is an opportunity, not a gap

Agentic tools in 2026 are increasingly *issue-driven*: you assign a ticket to an agent and it opens a PR. Since you have GitHub Team already, **GitHub Projects + Issues** is the obvious choice — it is included in your plan, and it is the substrate that Copilot's coding agent, Claude Code's GitHub Action, and Codex all plug into natively. Choosing Jira or Trello here would add an integration layer you do not need.

---

## 2. Options evaluated

### Option A — GitHub Copilot Business

The default recommendation for a GitHub-centric shop. ~$19/user/month for Business, which now includes a pooled allowance of GitHub AI Credits.

**Fit for your stack:** Very high. Official Eclipse plugin, native GitHub Actions and PR integration, an autonomous coding agent that can be assigned an issue and return a PR, and agentic code review that gathers project context before commenting.

**Pros**
- Only mainstream *agentic* tool with a first-party Eclipse plugin — no IDE migration.
- Deepest GitHub integration: issues → agent → PR → Actions → review, all inside tooling you already pay for.
- IP indemnity and admin policy controls on Business, which matters for a commercial codebase.
- Multi-model: Anthropic, OpenAI, and Google models selectable per task.
- Code completions and next-edit suggestions do **not** consume credits, so baseline autocomplete cost is predictable.
- Org-wide custom instructions let you encode Spring Boot conventions, Angular style, and MySQL patterns once.

**Cons**
- June 2026 billing change to usage-based AI Credits makes team-scale cost genuinely hard to forecast; chat, agents, and review all draw down the pool. Budget for overage and set admin spend caps *before* rollout.
- The Eclipse plugin lags the VS Code extension in feature parity — agent mode and newer capabilities land in VS Code first.
- Agent quality on large multi-module Maven/Gradle Spring projects is good but not best-in-class for long-horizon refactors.
- Seat sprawl: per-user pricing creeps as QA, leads, and contractors ask for access.

---

### Option B — Claude Code (Anthropic)

A terminal- and IDE-native agentic tool that reads the codebase, edits files, runs commands, and integrates with dev tooling. Available in terminal, IDE extensions, desktop app, and web.

**Fit for your stack:** High, provided you accept it running *beside* Eclipse rather than inside it. Its CLI-first design actually suits your Git Bash preference well.

**Pros**
- Currently the strongest published results on repository-scale coding benchmarks (SWE-bench Verified), and generally the pick for long-horizon multi-file work — exactly the shape of a Spring Boot service refactor or an Angular module rewrite.
- IDE-agnostic. Runs in Git Bash on Windows 11 or in a container; your Java devs keep Eclipse, your Angular devs can move to VS Code, everyone uses the same agent.
- `CLAUDE.md` files let you commit team standards, architecture decisions, and review checklists into the repo so the agent follows your conventions — versioned like any other artefact.
- MCP support connects it to external systems (Jira, Drive, custom tooling) if you later need it.
- Runs as a GitHub Action for automated PR review and issue-to-PR workflows on your existing pipeline.
- Skills and hooks let you package repeatable workflows (`/review-pr`, `/deploy-staging`) and share them across the team.

**Cons**
- **No Eclipse plugin.** Terminal or VS Code only — a real friction point for Eclipse-only Java developers.
- Team plan seat structure is the common budgeting trap: the entry-level Team seat does *not* include Claude Code; that requires the higher-tier Premium seat (roughly $100–125/seat/month, 5-seat minimum) or individual Pro/Max subscriptions. For 10 developers this is likely your most expensive per-seat option.
- Usage limits are expressed as multipliers rather than published token counts, so capacity planning is imprecise.
- Powerful autonomy means weak review discipline is punished quickly — you need guardrails from day one.

---

### Option C — OpenAI Codex

Terminal-native agent that reads the local repo, writes files, runs tests, and commits. Included with ChatGPT Plus/Business subscriptions, with token overflow billed at API rates.

**Fit for your stack:** Good if the team already has ChatGPT seats; otherwise it competes directly with Claude Code without a clear edge for your workload.

**Pros**
- Leads terminal-focused benchmarks (Terminal-Bench), which maps well to build/test/deploy automation — Maven builds, Tomcat deploys, Actions debugging.
- Bundled with ChatGPT subscriptions, so marginal cost may be near zero if seats already exist.
- MCP support and reusable "Skills" for custom workflows; multi-agent orchestration with git worktrees for safe parallel edits.
- Open-source CLI — inspectable, scriptable, easy to wire into Actions.

**Cons**
- No Eclipse integration; CLI-only workflow.
- Included credit allowance is modest; sustained agentic use spills into API-rate billing.
- Weaker on very large repository-wide reasoning than Claude Code by current public benchmarks.
- Less mature enterprise admin/governance tooling than Copilot Business.

---

### Option D — Amazon Q Developer / Kiro (AWS-native)

Q Developer is AWS's assistant with an Eclipse plugin and agentic capabilities; Kiro is Amazon's newer spec-driven agentic IDE (a VS Code fork, running Claude models via Bedrock).

**Fit for your stack:** Tempting because of AWS EC2 targeting and the Java angle — but the roadmap risk is significant.

**Pros**
- **Java transformation agents are the standout feature**: Amazon used them to upgrade ~1,000 Java 8 applications to Java 17 internally in two days. If you have a JDK or Spring Boot major-version upgrade pending, this is a strong, narrow reason to trial it.
- Deepest AWS integration of any tool — EC2, IAM, CloudFormation, and deployment context are first-class.
- Built-in security scanning with suggested fixes.
- Q Developer has a genuine Eclipse plugin today; free tier available for evaluation.
- Kiro's spec-driven model (requirements → design → tasks) suits a 10-person team that wants traceability from ticket to code.

**Cons**
- **AWS has announced end of support for Q Developer IDE plugins on 30 April 2027** and is steering users to Kiro. Adopting the Eclipse plugin now buys you roughly 20 months before a forced migration.
- Kiro is a separate VS Code-fork IDE — no Eclipse path at all, and credit-based pricing that scales with usage.
- Limited value outside AWS; weaker general-purpose Angular/TypeScript performance than the leaders.
- Much smaller community and ecosystem than Copilot or Claude Code.

---

### Option E — Cursor

The most widely deployed agentic IDE, a VS Code fork with strong multi-file editing and its Composer agent.

**Pros**
- Excellent agentic UX; strong at the multi-file, cross-layer changes typical of Angular-to-Spring-Boot feature work.
- VS Code fork, so existing VS Code extensions and Angular tooling transfer directly.
- Competitive price-per-output relative to the premium agents.

**Cons**
- **Requires abandoning Eclipse entirely** — the largest change-management cost of any option here.
- **Ownership uncertainty:** SpaceX agreed in June 2026 to acquire Anysphere (Cursor's parent) for $60B in an all-stock deal expected to close in Q3 2026, folding it into the xAI ecosystem. Expect model-routing, pricing, and data-handling changes. For a team standardising for the next few years, that is a real risk to weigh — and worth checking against your organisation's vendor and data-governance posture.
- Market share reportedly slipped through 2025–26 despite revenue growth, so the "safe default" argument is weaker than it was.

---

### Option F — Devin Desktop (formerly Windsurf) / Devin

Cognition rebranded Windsurf to Devin Desktop; the older Cascade agent reached end of life on 1 July 2026, with Devin Local now the default. Devin cloud agents handle asynchronous background tasks.

**Pros**
- Agent Command Center gives a Kanban-style view of every local and cloud agent — genuinely useful if you want a work board and an agent queue in one place.
- Asynchronous cloud agents suit "delegate the boring ticket overnight" workflows.
- Free tier plus Pro (~$20/mo) and Max (~$200/mo); cloud agent access starts at Pro.

**Cons**
- No Eclipse support; IDE migration required.
- Rapid product churn — a rebrand and an agent EOL within twelve months. Smaller ecosystem than Cursor or Copilot.
- Multi-agent orchestration is new and immature; not what I'd standardise a 10-person team on today.

---

### Option G — Tabnine

The conservative, compliance-first choice.

**Pros**
- Widest IDE coverage including Eclipse — no tooling change at all.
- Trained on permissively licensed code; deliberately conservative suggestions, good for codebases with strict style standards.
- Air-gapped / self-hosted deployment with zero code retention — the strongest option if your data-residency or client-contract requirements are tight.
- Cheap (~$9/user/month Pro).

**Cons**
- Primarily completion-focused; **not a true agent**. It will not take a ticket and return a PR.
- Materially behind on agentic capability — this is a productivity nudge, not an acceleration lever.
- Note that the Eclipse plugin is not onboarding new users, so verify current availability before planning around it.

---

### Option H — Open-source / BYOK agents (Cline, Continue, Aider, OpenCode)

Free tooling where you supply your own model API keys.

**Pros**
- No per-seat licence; you pay only for tokens actually consumed — often the cheapest route at 10 developers if usage is bursty.
- Model-neutral: route cheap models for boilerplate, premium models for hard problems. Direct cost control.
- Continue has an Eclipse-adjacent story via community plugins; Aider and OpenCode are CLI-native and IDE-agnostic.
- No vendor lock-in as the market consolidates.

**Cons**
- No indemnity, no support contract, no central admin or audit controls — a real gap for a commercial product.
- Someone on the team must own configuration, key management, and upgrades. At 10 developers that overhead is not trivial.
- Inconsistent quality and UX compared with commercial tools; onboarding cost per developer is higher.

---

## 3. Side-by-side summary

| Tool | Eclipse | True agent | GitHub-native | AWS-native | Indicative cost (10 devs/mo) | Main risk |
|---|---|---|---|---|---|---|
| **Copilot Business** | ✅ Official | ✅ | ✅ Best in class | ➖ | ~$190 + credit overage | Unpredictable credit spend |
| **Claude Code** | ❌ CLI/VS Code | ✅ Strongest | ✅ Via Action | ➖ | ~$1,000+ (Premium seats) | Cost; no Eclipse plugin |
| **OpenAI Codex** | ❌ CLI | ✅ | ➖ Good | ➖ | ~$200 if ChatGPT seats exist | Overflow token billing |
| **Amazon Q Developer** | ✅ (EOL Apr 2027) | ✅ | ➖ | ✅ Best | ~$190 (Pro) | Announced plugin EOL |
| **Kiro** | ❌ Own IDE | ✅ | ➖ | ✅ | Credit-based, variable | New product, IDE switch |
| **Cursor** | ❌ Own IDE | ✅ | ➖ | ➖ | ~$200–400 | Ownership change (SpaceX) |
| **Devin Desktop** | ❌ Own IDE | ✅ | ➖ | ➖ | ~$200+ | Product churn |
| **Tabnine** | ✅ | ❌ | ➖ | ➖ | ~$90 | Not agentic |
| **Open source (BYOK)** | Partial | ✅ | Varies | Varies | Token cost only | No support/indemnity |

---

## 4. Recommended approach

Rather than picking one winner, the pattern that works for teams your size is **layering**: an in-editor assistant for flow-state work, plus an agent for delegated multi-file tasks and PR review.

### Recommended combination

**Layer 1 — GitHub Copilot Business for all 10 seats (~$190/month).**
It is the only agentic option that works inside Eclipse today, it plugs straight into the GitHub Team + Actions pipeline you already run, and it carries IP indemnity. This is the safe floor.

**Layer 2 — Claude Code or Codex for 2–3 senior developers (~$200–300/month).**
Give your strongest developers a genuine repository-scale agent for the hard work: cross-cutting refactors, the Angular-to-API contract changes, test backfill, and the Tomcat/EC2 deployment automation. Both run in Git Bash beside Eclipse, so nobody has to switch IDEs. This is where the actual acceleration comes from.

**Layer 3 — GitHub Projects for the work board (included).**
Define this before rolling out agents, not after. Agent workflows in 2026 are issue-driven; without a board, "assign this ticket to an agent" has nothing to point at.

**Optional — trial Amazon Q Developer's Java transformation agent** as a *time-boxed project*, not a standing tool, if you have a JDK or Spring Boot upgrade on the roadmap. Use it, get the value, and don't build a dependency on a plugin with an announced 2027 EOL.

### Suggested rollout sequence

1. **Weeks 1–2 — Foundations.** Stand up GitHub Projects. Write the repo conventions file (`.github/copilot-instructions.md` and/or `CLAUDE.md`) covering your Spring Boot layering, Angular style guide, MySQL migration approach, and test expectations. This single artefact does more for output quality than any tool choice.
2. **Weeks 3–4 — Copilot pilot.** Three developers (one Angular, one Java, one full-stack). Install the Eclipse plugin. Set admin spend caps immediately.
3. **Weeks 5–8 — Agent pilot.** Two seniors on Claude Code or Codex, scoped to a defined slice of work (e.g. test coverage backfill, or a single Spring Boot module refactor). Measure against a control.
4. **Week 9 — Decide and scale.** Roll out the layer that demonstrably paid for itself.

### Governance to set before, not after

- **Mandatory human review on all AI-authored PRs.** Developer trust in AI output has been falling, not rising — review is not optional. Copilot's own framing is "copilot, not autopilot."
- **Branch protection + required CI checks in Actions** so no agent-authored change reaches EC2 unreviewed.
- **Spend caps and model routing policy** — cheap models for boilerplate, premium models for hard problems. Assume 50%+ above sticker price if agentic features are used daily.
- **Secrets and data policy.** Confirm what leaves your network, particularly for anything touching MySQL schemas or production configuration.
- **A "no agent" list** — authentication, payment paths, and DB migration scripts should stay human-authored or human-rewritten.

---

## 5. What to watch

The market is consolidating fast and every figure in this document has a short shelf life. Specifically:

- Cursor's SpaceX/xAI acquisition closing in Q3 2026, and what it does to pricing and data handling.
- The Amazon Q Developer plugin EOL in April 2027 and whether Kiro gains an Eclipse or JetBrains path.
- Copilot's AI Credits model settling — the promotional Business/Enterprise credit multipliers ran through August 2026, so budgets need re-forecasting now.
- Whether Copilot's Eclipse plugin closes the feature gap with the VS Code extension. If it does not, the case for moving your Angular developers to VS Code strengthens considerably.

---

## Sources to verify pricing against

- GitHub Copilot plans: https://github.com/features/copilot/plans
- Claude Code: https://code.claude.com/docs/en/overview and https://claude.com/product/claude-code
- Amazon Q Developer: https://aws.amazon.com/q/developer/
- Eclipse Marketplace (AI plugins): https://marketplace.eclipse.org/free-tagging/artificial-intelligence
