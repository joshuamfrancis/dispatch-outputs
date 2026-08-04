# AI Coding Assistant Options for Spring Boot / Angular Team

**Context:** 10 developers, Spring Boot + Java + Maven REST APIs, MySQL, Angular frontend, GitHub for source control, AWS for hosting, Eclipse as IDE.

The biggest constraint in this setup isn't the AI — it's Eclipse. Most of the strongest 2026 tools (Cursor, Windsurf, Kiro) are VS Code forks, so adopting them means changing IDE. Only Copilot has a first-class Eclipse plugin.

---

## Works in Eclipse today

### GitHub Copilot
The obvious default given the team is already on GitHub.

- The Eclipse plugin supports completions, Next Edit Suggestions, Ask/Agent Mode, MCP integration, and custom/subagents.
- Requires Eclipse 2024-09 or higher.
- **Pros:** cheapest path, org-level policy controls, code review + PR agents on GitHub itself, Business/Enterprise tiers with IP indemnity.
- **Pricing:** roughly $21–39/user/month at enterprise tier.
- **Cons:** the Eclipse plugin trails the VS Code version by months on features; marketplace reviews show real stability complaints.

### Tabnine
Relevant only if there are data-residency or air-gap requirements.

- Now enterprise-only with self-hosted deployment.
- Suggestion quality is notably weaker than cloud alternatives on complex architectural tasks.

---

## Worth it, but means leaving Eclipse

### Cursor
- Generally benchmarks highest on refactoring and agentic work.
- For a Spring Boot monolith plus an Angular app, whole-repo context is where the difference would be felt most.
- **Cost:** retraining 10 devs off Eclipse.

### Claude Code / Codex CLI
- Terminal-based, so IDE-agnostic — runs alongside Eclipse without replacing it.
- Good fit for Maven builds, test generation, and migration work.
- Weaker for inline autocomplete.

### Kiro (AWS)
- Relevant since the app is hosted on AWS.
- Official successor to Amazon Q Developer, which stopped new signups May 15, 2026 and ends support April 30, 2027.
- Differentiator: spec-driven development — structured requirements generated before code.
- **Recommendation:** don't start new adoption on Q Developer now.

---

## Devin (different category)

Devin is an autonomous agent that opens PRs, not an in-IDE assistant.

- Pricing restructured in June 2026: Free / Pro $20 / Max $200 / Teams $80 base + $40 per seat, enterprise on ACU contracts.
- Works well for well-scoped, repetitive tasks.
- Burns budget producing confident wrong output on ambiguous or architecture-heavy work.
- Treat as a backlog-clearing supplement, not a primary tool.

---

## Recommendation

1. **Start with GitHub Copilot Business** — lowest friction, no IDE migration, integrates with the existing GitHub workflow.
2. **Run a 60-day pilot** with 2–3 developers on Cursor or Claude Code in parallel to test whether the productivity gain justifies moving off Eclipse.
3. **Add Devin later**, only if there's a well-defined backlog to delegate to it.
4. **Decide code review governance up front** for AI-generated code — this affects outcomes more than which tool is chosen.

---

*Notes: AWS is retiring Amazon Q Developer (new signups blocked May 15, 2026; full end-of-support April 30, 2027). Pricing and product details reflect information available as of August 2026 and should be reverified before purchase decisions.*

---

# IDE Options for the Team

For a Spring Boot/Maven/MySQL backend + Angular frontend team, the realistic IDE choices are Eclipse (current), Spring Tool Suite (STS, an Eclipse distribution), IntelliJ IDEA, and VS Code. Each has different tradeoffs for AI agent compatibility.

## Eclipse (plain)
General-purpose Eclipse with Java/Maven tooling added manually.

- **Pros:** Free, team already knows it, huge plugin ecosystem, no licensing cost.
- **Cons:** No Spring-specific tooling out of the box (no Spring Boot config assist, bean graphs, live app view); heavier setup/maintenance per developer.
- **AI agent compatibility:** GitHub Copilot has an official Eclipse plugin (completions, chat, Agent Mode, MCP support, requires Eclipse 2024-09+). Copilot4Eclipse is a free third-party alternative. Cursor, Windsurf, and Kiro are not available in Eclipse — those require switching editors.

## Spring Tool Suite (STS) — *recommended over plain Eclipse*
STS is Pivotal/VMware's Eclipse distribution purpose-built for Spring, now rebranded "Spring Tools 5."

- **Pros:** Everything plain Eclipse offers, plus Spring Boot dashboard, bean/property auto-complete, live application view, Spring Initializr integration, and — as of Spring Tools 5.0 (Dec 2025) — it's explicitly built to be AI-native: it recognizes and integrates with Copilot and Cursor, adds an embedded MCP server, code lenses that explain Spring annotations, and Spring-aware context for AI chat.
- **Cons:** Slower to adopt new Eclipse platform releases than vanilla Eclipse; Spring-only (no benefit for the Angular side); heavier install.
- **AI agent compatibility:** Same Copilot Eclipse plugin works here, but STS adds Spring-specific value: code lenses that explain SpEL expressions and AOP annotations via Copilot, and an embedded MCP server that feeds Spring project structure to whichever AI agent you connect (Copilot, Cursor, or CLI agents like Claude Code). This is the best "stay in Eclipse family" option for AI-assisted Spring work.
- **Migration cost:** Low — STS is an Eclipse distribution, not a different IDE. Existing Eclipse muscle memory carries over.

## IntelliJ IDEA (Ultimate)
JetBrains' commercial Java IDE, widely considered the strongest for Spring/Java specifically.

- **Pros:** Best-in-class Java/Spring refactoring, inspections, and framework awareness; Spring Boot run dashboard and endpoint navigation built in; also supports Angular/TypeScript reasonably well in one IDE.
- **Cons:** Paid license (~$170/yr Ultimate, or ~$250/yr All Products Pack); JetBrains AI Assistant is billed separately on top of that (~$10–30/mo per dev); real retraining cost for a 10-person Eclipse team.
- **AI agent compatibility:** Strongest of the four options. Native JetBrains AI Assistant + Junie (autonomous agent, plan→execute→verify loop) is deeply integrated with the IDE's semantic model. As of IntelliJ 2026.1, it also natively supports Copilot, Cursor, Codex, and any Agent Client Protocol (ACP)–compatible agent — so you're not locked into JetBrains' own AI. Best semantic depth for Java specifically, but at the highest combined licensing cost.

## VS Code
Microsoft's free, extensible editor — the base that Cursor, Windsurf, and Kiro all fork from.

- **Pros:** Free, lightest weight, largest AI-tool ecosystem (every major AI coding tool supports VS Code first), good Angular/TypeScript support out of the box, huge extension marketplace including Spring Boot Tools and Java Extension Pack.
- **Cons:** Java tooling (via Red Hat's Java Language Server / Extension Pack for Java) is solid but generally regarded as less polished than IntelliJ's or Eclipse/STS's for large enterprise Spring codebases; more manual assembly of the "IDE" experience from extensions.
- **AI agent compatibility:** Best/broadest of all four — Copilot's flagship experience is built for VS Code first, and Spring Tools 5's Spring Boot extension is also available for VS Code with the same AI integrations as Eclipse/STS. If you ever want to trial Cursor or Windsurf, VS Code familiarity transfers directly since both are VS Code forks.

---

## Summary Table

| IDE | Cost | Spring-specific tooling | AI agent support | Migration effort from Eclipse |
|---|---|---|---|---|
| Eclipse (plain) | Free | Manual setup | Copilot only | None (status quo) |
| **STS (Spring Tools)** | Free | Excellent | Copilot, Cursor, MCP, CLI agents | Very low — same IDE family |
| IntelliJ IDEA Ultimate | ~$170–250/yr + AI add-on | Excellent | Broadest native + Copilot/Cursor/Codex via ACP | High |
| VS Code | Free | Good (via extensions) | Broadest overall — first-class for every AI tool | Moderate |

## Recommendation
Given the team is already on Eclipse: **migrate to STS first** — it's a near-zero-cost, near-zero-retraining swap that adds Spring-specific tooling and better AI integration (embedded MCP server, Copilot/Cursor support) without leaving the Eclipse family. Pair that with the Copilot Business rollout already recommended above. Treat IntelliJ and VS Code as longer-term options to pilot separately if the team wants deeper AI agent flexibility or better Angular tooling in the same window.
