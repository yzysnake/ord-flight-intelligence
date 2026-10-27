# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

This project combines data engineering, modeling and a public website, and depends on external data with very different licence terms. Choices about storage, orchestration and data providers have long-lived consequences, especially for licence compliance and point-in-time correctness. They must stay explainable later.

## Options considered

1. **No formal record:** decisions live in commits and chat history. Cheap, but rationale is lost.
2. **Lightweight ADRs in the repository:** one short Markdown file per decision, reviewed in a PR.

## Decision

Use lightweight ADRs in `docs/adr/`, following the template in `0000-template.md`. They are numbered sequentially and never rewritten once accepted; changes happen through superseding ADRs.

## Consequences

Each significant decision costs a few minutes of writing. In return, the reasoning behind provider, storage and tooling choices stays reviewable. That matters for licence audits and for revisiting decisions when prices or terms change.
