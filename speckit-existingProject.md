# How to integrate spec-kit into an existing project ?

## Constitution



## Project-level specifications

* here the _project folder contains all the constraints
  * note that constituion.md provides high level principles that governs the project. It should be stable
  * _project defines the project constraints. They can evolve with the project.

```
/specs/
  /_project/
    context.md
    constraints.md
    architecture.md
    standards.md
    glossary.md
  /features/
    2025-12-new-billing-flow/
      spec.md
      research.md
      plan.md
      data-model.md
      /contracts/
      quickstart.md
```


### `context.md` (what the project is)

* business/domain summary
* main user types & journeys
* what’s in/out of scope for the product

### `constraints.md` (non-negotiables)

* compliance/security constraints (PII, GDPR, SOC2, etc.)
* performance budgets
* supported browsers/devices
* accessibility level
* deployment/runtime constraints
* tech you *must* use / *must not* use

### `architecture.md` (how it’s built today)

* high-level diagram (even ASCII is fine)
* modules/services boundaries
* data sources
* key integration points
* where to add new code (folder map)

### `standards.md` (how you build here)

* coding conventions / lint / formatting
* testing rules (unit vs integration)
* branching/release strategy
* observability (logging, tracing, metrics)
* API conventions (REST/GraphQL patterns)

### `glossary.md` (domain vocabulary)

* domain terms
* canonical entity names
* event names (if event-driven)
* “don’t call it X, call it Y” rules

This set becomes the **baseline** every new spec should reference.

## Simpler solution

Two extra files that pay off long term:

### `decisions.md` (mini ADR log)

Record major decisions once:

* “We use X for auth because…”
* “We don’t allow Y in frontend because…”

### `constraints-registry.md`

A numbered list of constraints so you can reference them in plan/tasks:

```md
C-01: All UI must meet WCAG AA
C-02: Only PostgreSQL as source of truth
C-03: No PII in logs
C-04: Must use Design System tokens
```

## Spec Integration

At the top of every spec.md you can incorporate 

```
## Project baseline (authoritative)

This feature MUST comply with the following project-level specifications:

- Project context: ../../_project/context.md
- Global constraints: ../../_project/constraints.md
- Architecture baseline: ../../_project/architecture.md
- Engineering standards: ../../_project/standards.md
- Domain glossary: ../../_project/glossary.md

These documents are authoritative and must be treated as constraints,
not suggestions.
```

You could as well add it in plan.md as a hard guardrail

# Spec kit recommendations

* [Reference](https://www.youtube.com/watch?v=SGHIQTsPzuY)
* you may try difference models (GPT, Claude, Gemini)
* define the constitution
  * in the prompt you can give rules you may want to have in the constitution
  * you might give it the nature of the project (API REST, event driven)
  * you might give him the main technos (for example, i'm building on AWS but use Terraform for CI/CD). These are constraints not specific to a project but scope multiple projects
  * you might give him all the things you don't want to change, you want to keep it exactly as it is in terms of code organization, but be careful in the prompt to not be to rigid. He should able to modify exsiting files and add new files. It's just the structure principle that is fixed.
  * Don't be too rigid because constitution is the non negotiable rules