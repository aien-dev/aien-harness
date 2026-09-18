# aien-harness

Autonomous Change-Management, Schema Validation, and Eval Reliability Harness for AI Agents.

## Doctrine

The model does not own the standard. The harness does. Changing GPT, GLM, Lightning, or any other underlying model must not change what the agent accepts or delivers.

Based on Simon Høiberg’s 5-layer change-management framework, `aien-harness` enforces software-owned boundaries around autonomous agents:

1. **Layer 1: Eval Classifiers** — Splits producing work from judging work. Deterministic checks (syntax, slop phrases, test suites) are regular code. Subjective judgment calls a dedicated classifier judge (e.g. Qwen3-8B on port 18088).
2. **Layer 2: Schema Contracts** — "Done" is a validated JSON schema, not a conversational agreement. Required fields, evidence formats, and reproduction steps are checked by code.
3. **Layer 3: Least Privilege Tools** — Single-purpose actions with permissions lived in software, never in the system prompt.
4. **Layer 4: Deterministic Workflows** — Software owns the state sequence (`workflow_start`, `workflow_advance`, `deliver`). The model cannot skip tests or declare victory prematurely.
5. **Layer 5: Failure Replay** — Every painful failure is recorded with its task, bad output, and the eval that caught it. Changes cannot ship if old failure cases regress.

## Tools (MCP Stdio & FastMCP)

The harness exposes the following tools to Claude Code, Codex, Antigravity, and AIEN:
- `schema_validate`: Validate arbitrary payloads against strict JSON schemas.
- `eval_run`: Run deterministic or model-judged evaluations against work artifacts.
- `workflow_start` / `workflow_status` / `workflow_advance`: Enforce multi-step execution graphs.
- `deliver`: Verify all prerequisite schemas and evals have passed before output delivery.
- `failure_record` / `failure_list` / `failure_replay`: Regression test suite preserving past hurts.

## Quickstart

```bash
# Run standalone test
python3 server.py --test

# Run MCP server on stdio
python3 server.py
```

## Structure

- `schemas/`: JSON schemas defining finished states.
- `evals.json`: Classification rules and validation boundaries.
- `workflows.json`: Valid state transition graphs.
- `failures/`: Replay catalog of past regressions.
- `kb/`: Knowledge base lessons tied to failures.

## License

MIT OR Apache-2.0
