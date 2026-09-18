# python-empty-output

- severity: bad
- hurt: kernel returned no evidence
- lesson: Python pipeline results need a nonempty evidence list; do not only tweak the prompt.
- eval: required_evidence
- evidence: {"goal": "count", "code": "print(1)", "stdout": "", "ok": "false", "evidence": []}
- prompt_change: not the primary fix; update Cortex and this file instead
