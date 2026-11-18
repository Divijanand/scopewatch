# How AI and JetBrains tools built Scopewatch

A running log, written as the work happens. Each entry names the tool, the task, and what changed, with the commit.

## Tools
- **Claude Code** (Anthropic): engine v1–v2, metrics, map calibration, UI, docs. Commits are co-authored.
- **PyCharm**: shared run configurations are in the repo; _usage to be logged as it happens._
- **Junie / JetBrains Air**: _to be logged as features are built with them._

## Log

| Date | Tool | Task | Result |
|---|---|---|---|
| 2026-11-17 | Claude Code | Engine v2: reversal-safe ingest, metric registry, evidence API and UI | `21ef371` |
| 2026-11-18 | Claude Code | In-game minimaps with landmark calibration | `4874190` |
| 2026-11-18 | Claude Code | Callout-based findings, VOD links, Operator gamble, site executes | `cd81af1`, `c2de0a9`, `e5a351d` |
| 2026-11-18 | Claude Code | PyCharm run configurations, AGENTS.md for Junie/Air | _this commit_ |
