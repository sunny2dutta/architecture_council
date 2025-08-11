
import json, os, time, hashlib
from typing import Any, Dict, List, Optional

class TraceLogger:
    """Append-only JSONL logger for rich decision traces."""
    def __init__(self, path: str = "logs/decision_traces.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _write(self, obj: Dict[str, Any]):
        obj['ts'] = int(time.time())
        with open(self.path, 'a') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def start_decision(self, brief: Dict[str, Any]) -> str:
        did = hashlib.sha1((brief.get('title','') + str(time.time())).encode()).hexdigest()[:16]
        self._write({"type":"decision_start", "decision_id": did, "brief": brief})
        return did

    def log_agent_card(self, decision_id: str, agent: str, card: Dict[str, Any]):
        safe_card = dict(card)
        # Avoid logging verbose chain-of-thought; keep short rationale only if present
        if 'rationale_summary' in safe_card and isinstance(safe_card['rationale_summary'], str):
            if len(safe_card['rationale_summary']) > 500:
                safe_card['rationale_summary'] = safe_card['rationale_summary'][:500] + "..."
        self._write({"type":"agent_scorecard", "decision_id": decision_id, "agent": agent, "scorecard": safe_card})

    def log_uncertainty(self, decision_id: str, before: Dict[str, float], after: Dict[str, float]):
        self._write({"type":"uncertainty_update", "decision_id": decision_id, "before": before, "after": after})

    def log_question_ranking(self, decision_id: str, ranked: List[Dict[str, Any]]):
        self._write({"type":"question_ranking", "decision_id": decision_id, "ranked": ranked})

    def log_policy_decision(self, decision_id: str, route: str, reason: str, edr: float, ig_star: float):
        self._write({"type":"policy_decision", "decision_id": decision_id, "route": route, "reason": reason, "edr": edr, "ig_star": ig_star})

    def log_design_artifacts(self, decision_id: str, containers: List[Dict[str, Any]], adrs: List[Dict[str, Any]]):
        self._write({"type":"design_artifacts", "decision_id": decision_id, "containers": containers, "adrs": adrs})

    def end_decision(self, decision_id: str):
        self._write({"type":"decision_end", "decision_id": decision_id})
