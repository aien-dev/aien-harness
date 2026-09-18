# Atlas change-management harness

Source: Simon Høiberg, “The AI System Behind My 7-Figure Business” (2026).
https://www.youtube.com/watch?v=tmVcfnNWXfQ

The model does not own Atlas’s standard. The harness does. Changing GPT, GLM, Fable, Lightning, or any other model must not change what Atlas accepts.

## Layer 1 — Eval classifiers

Split producing work from judging work. An eval checks one artifact against one standard and returns approved or rejected with reason and evidence.

- Deterministic evals are ordinary code (missing fields, slop phrases, failed tests).
- Judgment evals are a separate model call with one job: classify.
- The producing agent does not get to mark its own work done.

## Layer 2 — Schema contracts

“Done” is a schema, not a vibe. Required fields, formats, and evidence locations are software-checked. An agent may not invent its own definition of finished work.

## Layer 3 — Purpose-built tools (least privilege)

Each tool is one narrow company action. Permissions live in software, not in the system prompt. If a capability must not happen, no tool exists for it.

## Layer 4 — Deterministic workflows

The model judges inside a job. Software owns the sequence. Transition rules decide which state may follow another. The agent cannot skip reproduction, swap an easier test, or declare victory because a patch looks reasonable.

## Layer 5 — Failure replay

When a failure costs time, save the original task, the bad output, and the eval that should have rejected it. Before changing a model, tool, prompt, or eval, replay those cases. If an old failure comes back, the change does not ship.

## Operator rule for Atlas

Use `workflow_start` / `workflow_advance` for multi-step jobs. Call `deliver` only after schema validation and required evals pass. Record new hurts with `failure_record`. Run `failure_replay` before any harness or model change.

## Python lane

Prime Agent runs almost everything through a persistent Python REPL. Atlas does not. `route_task` sends computation, tests, parsing, and self-improvement of code to `python_exec` and workflow `python_pipeline`. Chat, Cortex, and image stay on tools. Hybrid work can use both.

A failed python_pipeline eval must `remember` (Cortex + `harness/kb`) before `refine`. The kernel holds variables across calls. `python_reset` starts a clean pipeline.

## Memory-first RSI

A bad failure becomes a replay case, a knowledge-base lesson, and a Cortex entity. Prompt text is not the system of record. Mild wording issues may still get a prompt tweak after the lesson is stored.

## Wiring

These layers live in `mcp/atlas/harness.py` and reach Atlas as MCP tools: `schema_validate`, `eval_run`, `workflow_start` / `workflow_status` / `workflow_advance`, `deliver`, `failure_record` / `failure_list` / `failure_replay`, and `kb_list` / `kb_read`. `agent_instructions.txt` tells Atlas to use them.

Judgment evals run on the Qwen3-8B judge at `127.0.0.1:18088`. If the judge is unreachable or returns no verdict, the eval returns `status: error`. That blocks `deliver` and fails `failure_replay`, so an outage cannot masquerade as a rejection.
