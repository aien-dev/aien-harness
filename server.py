"""The five-layer change-management harness: schemas, evals, workflows, failures, KB.

The model does not own Atlas's standard; this module does. It also exposes the
read-only TrueForge session review tools used to inspect what Atlas actually did.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any

from .app import _registry as mcp
from .config import CORTEX_URL, HARNESS, HARNESS_KEY_FILE, JUDGE_MODEL, JUDGE_TOKEN_FILE, JUDGE_URL, KB, STATE
from .cortex import _cortex_headers
from .http_util import _http, _verdict


def _judge_headers() -> dict[str, str]:
    token = JUDGE_TOKEN_FILE.read_text().strip() if JUDGE_TOKEN_FILE.is_file() else ""
    token = token or os.environ.get("ATLAS_JUDGE_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _load_json(path) -> Any:
    return json.loads(path.read_text())


def _evals() -> dict[str, Any]:
    return _load_json(HARNESS / "evals.json")


def _workflows() -> dict[str, Any]:
    return _load_json(HARNESS / "workflows.json")


def _schema(name: str) -> dict[str, Any]:
    path = HARNESS / "schemas" / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"unknown schema: {name}")
    return _load_json(path)


def _validate_schema(schema: dict[str, Any], artifact: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(artifact, dict):
            return [f"{path}: expected object"]
        for key in schema.get("required", []):
            if key not in artifact:
                errors.append(f"{path}.{key}: missing required field")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in artifact:
                if key not in props:
                    errors.append(f"{path}.{key}: unexpected field")
        for key, sub in props.items():
            if key in artifact:
                errors.extend(_validate_schema(sub, artifact[key], f"{path}.{key}"))
    elif expected == "array":
        if not isinstance(artifact, list):
            return [f"{path}: expected array"]
        min_items = schema.get("minItems", 0)
        if len(artifact) < min_items:
            errors.append(f"{path}: need at least {min_items} items")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(artifact):
                errors.extend(_validate_schema(item_schema, item, f"{path}[{i}]"))
    elif expected == "string":
        if not isinstance(artifact, str):
            return [f"{path}: expected string"]
        min_len = schema.get("minLength", 0)
        if len(artifact) < min_len:
            errors.append(f"{path}: shorter than {min_len}")
    return errors


def _slop_gate(text: str, spec: dict[str, Any]) -> tuple[str, str, list[str]]:
    hits: list[str] = []
    lower = text.lower()
    for phrase in spec.get("phrases", []):
        if phrase.lower() in lower:
            hits.append(phrase)
    if spec.get("not_x_its_y") and re.search(r"\bit'?s not\b.+\bit'?s\b", text, re.I | re.S):
        hits.append("it's not X, it's Y")
    if hits:
        return "rejected", "slop phrases present", hits
    return "approved", "no slop phrases", []


def _run_eval(name: str, artifact: Any) -> dict[str, Any]:
    spec = _evals().get(name)
    if not spec:
        return {"status": "rejected", "reason": f"unknown eval {name}", "evidence": None}
    if name == "slop_gate":
        text = artifact if isinstance(artifact, str) else json.dumps(artifact, ensure_ascii=False)
        status, reason, evidence = _slop_gate(text, spec)
        return {"eval": name, "status": status, "reason": reason, "evidence": evidence}
    if name == "required_evidence":
        evidence = None
        if isinstance(artifact, dict):
            evidence = artifact.get("evidence") or artifact.get("sources") or artifact.get("failure_evidence")
        ok = bool(evidence) and (not isinstance(evidence, list) or len(evidence) > 0)
        return {"eval": name, "status": "approved" if ok else "rejected", "reason": "evidence present" if ok else "evidence missing", "evidence": evidence}
    if name == "reproduction_present":
        if not isinstance(artifact, dict):
            return {"eval": name, "status": "rejected", "reason": "artifact must be an object", "evidence": None}
        steps = artifact.get("reproduction_steps") or []
        fail = artifact.get("failure_evidence") or ""
        ok = isinstance(steps, list) and len(steps) > 0 and all(str(s).strip() for s in steps) and str(fail).strip()
        return {"eval": name, "status": "approved" if ok else "rejected", "reason": "reproduction complete" if ok else "reproduction_steps or failure_evidence missing", "evidence": {"steps": steps, "failure_evidence": fail}}
    if name == "source_supports_claim":
        if isinstance(artifact, dict) and {"claim", "excerpt"} <= artifact.keys():
            prompt = spec["prompt"].format(claim=artifact.get("claim", ""), excerpt=artifact.get("excerpt", ""), url=artifact.get("url") or artifact.get("source_url", ""))
            body = {"model": JUDGE_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024, "temperature": 0}
            code, raw = _http("POST", JUDGE_URL, body, headers=_judge_headers(), timeout=60)
            if code >= 400:
                return {"eval": name, "status": "error", "reason": f"judge unavailable HTTP {code}", "evidence": raw[:500]}
            try:
                message = json.loads(raw)["choices"][0]["message"]
                content = (message.get("content") or "").strip()
                if not content:
                    content = (message.get("reasoning_content") or "").strip()
            except (KeyError, IndexError, json.JSONDecodeError):
                content = raw
            verdicts = re.findall(r"\b(APPROVED|REJECTED)\b(?:\s*:\s*(.*))?", content, flags=re.I)
            if not verdicts:
                return {"eval": name, "status": "error", "reason": "judge returned no APPROVED/REJECTED line", "evidence": content[:1000]}
            label, reason = verdicts[-1]
            return {"eval": name, "status": label.lower(), "reason": (reason or "").strip() or label.upper(), "evidence": content[:1000]}
        return {"eval": name, "status": "rejected", "reason": "need claim and excerpt", "evidence": None}
    return {"eval": name, "status": "rejected", "reason": f"eval {name} not implemented", "evidence": None}


def _remember(failure_id: str, hurt: str, lesson: str, evidence: Any, eval_name: str, severity: str) -> dict[str, Any]:
    kb_path = KB / f"{failure_id}.md"
    body = (
        f"# {failure_id}\n\n"
        f"- severity: {severity}\n"
        f"- hurt: {hurt}\n"
        f"- lesson: {lesson}\n"
        f"- eval: {eval_name}\n"
        f"- evidence: {json.dumps(evidence, ensure_ascii=False)[:4000]}\n"
        f"- prompt_change: not the primary fix; update Cortex and this file instead\n"
    )
    kb_path.write_text(body)
    cortex = {"skipped": True}
    if severity in {"bad", "severe"}:
        payload = {
            "kind": "entity",
            "value": {
                "canonicalName": f"atlas-lesson:{failure_id}"[:240],
                "content": f"Lesson from failure {failure_id} ({severity}). Hurt: {hurt}. Lesson: {lesson}. Keep this as working knowledge. Do not treat a prompt tweak as the fix.",
            },
        }
        code, raw = _http("POST", f"{CORTEX_URL}/api/cortex/write", payload, headers=_cortex_headers())
        cortex = {"http": code, "body": json.loads(raw) if raw.strip().startswith(("{", "[")) else raw[:1500]}
    return {"kb": str(kb_path), "cortex": cortex, "prompt_change": "skipped"}


def _harness_headers() -> dict[str, str]:
    try:
        token = HARNESS_KEY_FILE.read_text().strip()
    except OSError:
        return {}
    return {"Authorization": "Bearer " + token} if token else {}


@mcp.tool()
def harness_sessions(limit: int = 25) -> str:
    """List recent TrueForge sessions (id, title, updated). Entry point for reviewing what Atlas did."""
    code, body = _http("GET", "http://127.0.0.1:8791/api/v1/sessions?limit=%d" % max(limit, 1),
                       None, _harness_headers())
    if code != 200:
        return json.dumps({"error": "http %d" % code, "body": body[:500]})
    try:
        data = json.loads(body).get("data", [])
    except ValueError:
        return json.dumps({"error": "bad json"})
    return json.dumps([{"id": s.get("id"), "title": (s.get("title") or "")[:80],
                        "updated_at": s.get("updated_at")} for s in data])


@mcp.tool()
def harness_session_turns(session_id: str) -> str:
    """List turns of one session (id, status). Follow with harness_turn_events for content."""
    code, body = _http("GET", "http://127.0.0.1:8791/api/v1/sessions/%s/turns" % session_id,
                       None, _harness_headers())
    if code != 200:
        return json.dumps({"error": "http %d" % code, "body": body[:500]})
    try:
        data = json.loads(body).get("data", [])
    except ValueError:
        return json.dumps({"error": "bad json"})
    turns = data if isinstance(data, list) else []
    return json.dumps([{"id": t.get("id"), "status": t.get("status")} for t in turns])


@mcp.tool()
def harness_turn_events(session_id: str, turn_id: str, limit: int = 60) -> str:
    """Read a turn's events: user messages, model replies (with token usage), tool calls and results. Truncated excerpts for review, not full dumps."""
    code, body = _http("GET", "http://127.0.0.1:8791/api/v1/sessions/%s/turns/%s/events" % (session_id, turn_id),
                       None, _harness_headers())
    if code != 200:
        return json.dumps({"error": "http %d" % code, "body": body[:500]})
    try:
        data = json.loads(body).get("data", [])
    except ValueError:
        return json.dumps({"error": "bad json"})
    out = []
    for e in (data if isinstance(data, list) else [])[:max(limit, 1)]:
        t = e.get("type")
        if t == "model.message":
            m = e.get("data", e)
            content = m.get("content") if isinstance(m, dict) else None
            out.append({"type": t, "content": str(content or "")[:1500],
                        "tool_calls": bool((m.get("tool_calls") if isinstance(m, dict) else None))})
        elif t == "tool.response":
            out.append({"type": t, "content": str(e.get("content", ""))[:800]})
        else:
            out.append({"type": t})
    return json.dumps(out)


@mcp.tool()
def schema_list() -> str:
    """List named schema contracts the harness will enforce."""
    names = [p.stem for p in (HARNESS / "schemas").glob("*.json")]
    return json.dumps({"schemas": names})


@mcp.tool()
def schema_validate(schema_name: str, artifact_json: str) -> str:
    """Validate artifact_json against a named schema contract. Software, not the model, decides completeness."""
    artifact = json.loads(artifact_json)
    errors = _validate_schema(_schema(schema_name), artifact)
    status = "approved" if not errors else "rejected"
    return _verdict(status, "schema valid" if not errors else "schema invalid", errors)


@mcp.tool()
def eval_run(eval_name: str, artifact_json: str) -> str:
    """Run one named eval classifier against an artifact. Returns approved or rejected with evidence."""
    artifact = json.loads(artifact_json) if artifact_json.lstrip()[:1] in "{[" else artifact_json
    return json.dumps(_run_eval(eval_name, artifact), ensure_ascii=False)


@mcp.tool()
def workflow_start(workflow_name: str, goal: str) -> str:
    """Start a deterministic workflow. Software owns allowed state transitions."""
    spec = _workflows().get(workflow_name)
    if not spec:
        return json.dumps({"error": f"unknown workflow {workflow_name}"})
    job_id = str(uuid.uuid4())
    record = {
        "id": job_id,
        "workflow": workflow_name,
        "goal": goal,
        "state": spec["initial"],
        "history": [{"state": spec["initial"], "at": time.time()}],
    }
    (STATE / "workflows" / f"{job_id}.json").write_text(json.dumps(record, indent=2))
    return json.dumps(record)


@mcp.tool()
def workflow_status(job_id: str) -> str:
    """Read the current workflow job and its allowed next states."""
    path = STATE / "workflows" / f"{job_id}.json"
    if not path.is_file():
        return json.dumps({"error": "unknown job"})
    record = _load_json(path)
    spec = _workflows()[record["workflow"]]
    record["allowed_next"] = spec["states"][record["state"]]["next"]
    return json.dumps(record)


@mcp.tool()
def workflow_advance(job_id: str, next_state: str, evidence_json: str = "{}") -> str:
    """Advance a workflow only along an allowed transition. Evidence is stored on the history entry."""
    path = STATE / "workflows" / f"{job_id}.json"
    if not path.is_file():
        return json.dumps({"error": "unknown job"})
    record = _load_json(path)
    spec = _workflows()[record["workflow"]]
    allowed = spec["states"][record["state"]]["next"]
    if next_state not in allowed:
        return json.dumps({"error": "illegal transition", "from": record["state"], "requested": next_state, "allowed": allowed})
    evidence = json.loads(evidence_json) if evidence_json else {}
    record["state"] = next_state
    record["history"].append({"state": next_state, "at": time.time(), "evidence": evidence})
    path.write_text(json.dumps(record, indent=2))
    record["allowed_next"] = spec["states"][next_state]["next"]
    return json.dumps(record)


@mcp.tool()
def deliver(schema_name: str, artifact_json: str, eval_names_csv: str) -> str:
    """Accept finished work only if the schema and every named eval approve it."""
    artifact = json.loads(artifact_json)
    schema_errors = _validate_schema(_schema(schema_name), artifact)
    evals = []
    names = [n.strip() for n in eval_names_csv.split(",") if n.strip()]
    for name in names:
        evals.append(_run_eval(name, artifact if name != "slop_gate" else json.dumps(artifact)))
    rejected = schema_errors or any(item["status"] != "approved" for item in evals)
    receipt = {
        "id": str(uuid.uuid4()),
        "schema": schema_name,
        "accepted": not rejected,
        "schema_errors": schema_errors,
        "evals": evals,
        "artifact": artifact,
        "at": time.time(),
    }
    out = STATE / "deliveries" / f"{receipt['id']}.json"
    out.write_text(json.dumps(receipt, indent=2))
    return json.dumps({"accepted": receipt["accepted"], "receipt_id": receipt["id"], "schema_errors": schema_errors, "evals": evals, "path": str(out)})


@mcp.tool()
def failure_record(failure_id: str, hurt: str, eval_name: str, artifact_json: str, expect: str = "rejected", severity: str = "bad", lesson: str = "") -> str:
    """Save a failure as a replay case. For bad/severe failures, also write Cortex and the knowledge base. Do not treat a prompt edit as the fix."""
    artifact = json.loads(artifact_json) if artifact_json.lstrip()[:1] in "{[" else {"text": artifact_json}
    case = {"id": failure_id, "hurt": hurt, "eval": eval_name, "artifact": artifact, "expect": expect, "severity": severity, "lesson": lesson}
    path = HARNESS / "failures" / f"{failure_id}.json"
    path.write_text(json.dumps(case, indent=2) + "\n")
    remembered = _remember(failure_id, hurt, lesson or hurt, artifact, eval_name, severity)
    return json.dumps({"saved": str(path), "remembered": remembered})


@mcp.tool()
def failure_list() -> str:
    """List saved failure-replay cases."""
    cases = []
    for path in sorted((HARNESS / "failures").glob("*.json")):
        case = _load_json(path)
        cases.append({"id": case.get("id", path.stem), "hurt": case.get("hurt"), "eval": case.get("eval"), "expect": case.get("expect")})
    return json.dumps({"cases": cases})


@mcp.tool()
def failure_replay(failure_id: str = "") -> str:
    """Replay saved failures against current evals. A change must not ship if an old failure comes back."""
    paths = [HARNESS / "failures" / f"{failure_id}.json"] if failure_id else sorted((HARNESS / "failures").glob("*.json"))
    results = []
    failed = False
    for path in paths:
        if not path.is_file():
            results.append({"id": path.stem, "ok": False, "reason": "missing case"})
            failed = True
            continue
        case = _load_json(path)
        got = _run_eval(case["eval"], case["artifact"])
        expect = case.get("expect", "rejected")
        ok = got["status"] == expect
        failed = failed or not ok
        results.append({"id": case.get("id", path.stem), "ok": ok, "expect": expect, "got": got})
    return json.dumps({"passed": not failed, "results": results})


@mcp.tool()
def kb_list() -> str:
    """List knowledge-base lessons written from failures."""
    names = sorted(p.name for p in KB.glob("*.md"))
    return json.dumps({"lessons": names})


@mcp.tool()
def kb_read(name: str) -> str:
    """Read one knowledge-base lesson file."""
    path = KB / name
    if not path.is_file():
        path = KB / f"{name}.md"
    if not path.is_file():
        return json.dumps({"error": f"unknown lesson {name}"})
    return json.dumps({"name": path.name, "content": path.read_text()[:8000]})
