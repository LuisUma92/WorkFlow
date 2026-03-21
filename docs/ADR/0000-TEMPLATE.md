---
adr: XXXX
title: "<Short descriptive title>"
status: Proposed | Accepted | Superseded | Deprecated
date: YYYY-MM-DD
authors:
  - Name
reviewers: []
tags:
  - architecture
  - domain
  - infrastructure
decision_scope: system | module | component
supersedes: null
superseded_by: null
related_adrs: []
---

## Context

Describe the architectural problem or design pressure that motivates this decision.

Include relevant background:

- current system behavior
- architectural constraints
- integration requirements
- scalability expectations
- operational considerations

Explain **why a decision is required now**.

Agents and readers should be able to answer:

- What problem does this ADR solve?
- What constraints influence the decision?

---

## Decision Drivers

Key factors that influenced this decision.

Examples:

- maintainability
- simplicity
- performance
- observability
- architectural consistency
- operational reliability

List the most important drivers.

---

## Decision

Describe the architectural decision clearly.

Include:

- the chosen design
- architectural boundaries
- new interfaces or abstractions
- rules introduced by this decision

Example:

```python
class ExamplePort(Protocol):
    def execute(self, input: Input) -> Output:
        ...
```

This section must allow both humans and AI agents to determine:

- what must be implemented
- what architectural structure must be followed.

---

## Architectural Rules

Rules introduced by this ADR.

Use **RFC-style semantics**:

### MUST

Hard constraints that must never be violated.

Examples:

- Domain layer **MUST NOT** depend on infrastructure.
- Dependency injection **MUST occur only in `bootstrap.py`**.

### SHOULD

Recommended practices.

Examples:

- Parsers **SHOULD declare metadata attributes** (`bank`, `notification_type`).
- Adapters **SHOULD be located in `adapters/`**.

### MAY

Optional practices.

Examples:

- Additional validation **MAY be implemented in adapters**.
- Debug artifacts **MAY be stored under `data/`**.

---

## Implementation Notes

Guidance for developers and AI agents implementing this decision.

Examples:

- Where new code should live
- What interfaces must be implemented
- What patterns should be used

Example:

```
New message sources must implement:

MessageSourcePort
```

```
Adapters must live in:

src/bank_ingest/adapters/
```

This section helps prevent incorrect implementations.

---

## Impact on AI Coding Agents

Instructions specifically for automated code generation tools.

Agents modifying the codebase must follow these rules:

- Do not introduce dependencies that violate architectural layers.
- New infrastructure integrations must be implemented as adapters.
- Do not bypass ports defined in the domain or application layer.
- Register new parsers through the parser registry.

Agents should consult related ADRs before implementing major features.

---

## Consequences

### Benefits

Expected advantages:

- improved modularity
- clearer architecture
- easier testing
- maintainability

### Costs

Tradeoffs or drawbacks:

- additional architectural discipline
- more files or components
- higher upfront design effort

---

## Alternatives Considered

Document evaluated alternatives.

### Alternative A

Description.

#### Advantages

- benefits

#### Disadvantages

- reasons for rejection

---

## Compatibility / Migration

Describe whether the decision:

- requires refactoring
- is backward compatible
- introduces breaking changes

Example:

```
No migration required.
Applies only to new components.
```

---

## References

External references or documentation.

Examples:

- Alistair Cockburn — Hexagonal Architecture
- Eric Evans — Domain-Driven Design
- Robert C. Martin — Clean Architecture
- Martin Fowler — Architectural Decision Records

---

## Status

Record the state of the ADR.

Possible values:

- **Proposed**
- **Accepted**
- **Superseded**
- **Deprecated**

If superseded, reference the new ADR.

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| YYYY-MM-DD | Initial ADR |
