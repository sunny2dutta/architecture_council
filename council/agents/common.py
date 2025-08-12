# council/agents/common.py
from __future__ import annotations
import json
from typing import Dict, Any, Optional
from ..models import ProblemBrief

# Single source of truth for the Scorecard shape
SCHEMA_HINT: Dict[str, Any] = {
    "agent": "string",
    "assumptions": ["string"],
    "concerns": ["string"],
    "blockers": ["string"],
    "key_decisions": [{"topic":"string","options":["string"],"recommend":"string","rationale":"string"}],
    "question_candidates": [{"q":"string","expected_delta_U":{"k":"float"},"expected_delta_risk":"float"}],
    "design_deltas": [{"change":"string","impact":"string","cost":"string","category":"string","confidence":0.0}],
    "risk_score": 0.0,
    "uncertainty_updates": {"k":"float"},
    "rationale_summary": "≤50 words"
}

def render_prompt(role: str,
                  agent_name: str,
                  brief: ProblemBrief,
                  context: Optional[dict],
                  facts: Optional[dict],
                  rag: Optional[Dict[str, Any]] = None) -> str:
    """Builds the user prompt section; agents only supply role/agent_name."""
    return f"""
Role: {role}
Agent: {agent_name}

Problem:
title={brief.title}
description={brief.description}
constraints={brief.constraints}
must_haves={brief.must_haves}
metrics={brief.metrics}
timelines={brief.timelines}
known_risks={brief.known_risks}
unknowns={brief.unknowns}

User clarifications={json.dumps((context or {}).get("user_answers", {}), ensure_ascii=False)}
Derived hints={json.dumps((context or {}).get("derived", {}), ensure_ascii=False)}
Org facts={json.dumps(facts or {}, ensure_ascii=False)}
RAG snippets={json.dumps((rag or {}).get("snippets", []), ensure_ascii=False)}

Return a Scorecard JSON with fields (example types only):
{json.dumps(SCHEMA_HINT, indent=2)}
""".strip()
