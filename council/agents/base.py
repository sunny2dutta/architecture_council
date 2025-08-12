# council/agents/base.py
from __future__ import annotations
from typing import Dict, Any, Optional
import json
from ..models import ProblemBrief, Scorecard
from ..llm import DeepSeekClient
from .common import render_prompt

# Common output contract for all experts
OUTPUT_POLICY = """
Output policy:
- Return ONLY valid JSON for a Scorecard (no prose, no chain-of-thought).
- rationale_summary ≤ 50 words.
- risk_score in [0,1]
- uncertainty_updates values in [-1,1]
- question_candidates must include expected_delta_U (dict) and expected_delta_risk (float).
"""

def parse_json_safely(txt: str) -> Dict[str, Any]:
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        s = txt.find("{"); e = txt.rfind("}")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(txt[s:e+1])
            except Exception:
                pass
    return {}

class AgentBase:
    """All agents share this; subclasses only define name, role, and SYS_PROMPT."""
    name: str = "Agent"
    role: str = "Expert"
    SYS_PROMPT: str = f"You are an expert architect.\n{OUTPUT_POLICY}"
    max_tokens: int = 750  # override if a role needs more

    def __init__(self, client: DeepSeekClient):
        self.client = client

    # Hook for RAG later; override in a specific agent if needed
    def retrieve_knowledge(self, brief: ProblemBrief, context: Optional[dict], facts: Optional[dict]) -> Dict[str, Any]:
        return {}

    # Generic analyze: builds messages, calls LLM, parses JSON into Scorecard
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any],
                context: Optional[dict] = None,
                facts: Optional[dict] = None) -> Scorecard:
        rag = self.retrieve_knowledge(brief, context, facts)
        messages = [
            {"role": "system", "content": self.SYS_PROMPT},
            {"role": "user", "content": render_prompt(self.role, self.name, brief, context, facts, rag)},
        ]
        out = self.client.chat(messages, max_tokens=self.max_tokens, extra={"stream": False})
        obj = parse_json_safely(out["content"]) or {}
        # safe fill with dataclass defaults
        return Scorecard(agent=self.name, **{k: obj.get(k, v) for k, v in Scorecard(agent="x").__dict__.items() if k != "agent"})
