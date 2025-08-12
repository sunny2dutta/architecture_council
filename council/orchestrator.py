from typing import List, Dict, Any, Tuple, Callable, Optional
import re

from .models import ProblemBrief, DebateState, DecisionOutput, Scorecard
from .policy import DecisionPolicy
from .logging_ext import TraceLogger

AskCallback = Callable[[List[str]], Dict[str, str]]  # receives questions -> returns {question: answer}

# ---------- helpers to normalize user answers into structured hints ----------
_DURATION_UNITS = {
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600
}

def _normalize_duration_to_seconds(num: float, unit: str) -> int:
    unit = unit.lower()
    return int(float(num) * _DURATION_UNITS.get(unit, 1))

def _parse_duration(label: str, text: str) -> Optional[int]:
    # e.g., "RTO 2h", "rpo: 45 min"
    m = re.search(rf"\b{label}\b[:\s]*([0-9]+(?:\.[0-9]+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours)\b",
                  text, flags=re.I)
    if not m:
        return None
    return _normalize_duration_to_seconds(m.group(1), m.group(2))

def _parse_rps(text: str) -> Optional[int]:
    # e.g., "120 rps", "1.5k rps", "2m qps", "peak 10k"
    m = re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*([km])?\s*(rps|qps)\b", text, flags=re.I)
    if not m:
        m2 = re.search(r"\b(peak|traffic|load)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)([km])\b", text, flags=re.I)
        if not m2:
            return None
        val = float(m2.group(2)); mult = m2.group(3).lower()
    else:
        val = float(m.group(1)); mult = (m.group(2) or "").lower()
    if mult == "k":
        val *= 1_000
    elif mult == "m":
        val *= 1_000_000
    return int(val)

def _parse_latency_budget(text: str) -> Optional[int]:
    # e.g., "p95 300ms", "p99: 1s", "latency budget 800 ms"
    m = re.search(r"\b(p95|p99|latency(?:\s*budget)?)\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(ms|s)\b", text, flags=re.I)
    if not m:
        return None
    val = float(m.group(2)); unit = m.group(3).lower()
    return int(val if unit == "ms" else val * 1000)

def _normalize_residency(text: str) -> Optional[str]:
    if re.search(r"\beu[-\s]?only\b|\bdata must stay in eu\b|\bgdpr\b|\bresidency\b", text, flags=re.I):
        return "EU"
    if re.search(r"\bus[-\s]?only\b|\bdata must stay in us\b", text, flags=re.I):
        return "US"
    if re.search(r"\bin[-\s]?country\b|\blocal residency\b", text, flags=re.I):
        return "IN-COUNTRY"
    return None

def _parse_consistency(text: str) -> Optional[str]:
    for level in ("strong", "bounded staleness", "bounded-staleness", "eventual"):
        if re.search(level, text, flags=re.I):
            return level.replace(" ", "_").upper()
    return None

def _derive_from_answers(answers: Dict[str, str]) -> Dict[str, Any]:
    text = " ".join((answers or {}).values()).lower()
    derived: Dict[str, Any] = {}
    # Durations
    rto_s = _parse_duration("rto", text)
    rpo_s = _parse_duration("rpo", text)
    if rto_s is not None:
        derived["RTO_s"] = rto_s
    if rpo_s is not None:
        derived["RPO_s"] = rpo_s
    # Residency
    residency = _normalize_residency(text)
    if residency:
        derived["residency"] = residency
    # Traffic / latency
    peak_rps = _parse_rps(text)
    if peak_rps is not None:
        derived["peak_rps"] = peak_rps
    p95_ms = _parse_latency_budget(text)
    if p95_ms is not None:
        derived["p95_latency_ms"] = p95_ms
    # Consistency model
    consistency = _parse_consistency(text)
    if consistency:
        derived["consistency"] = consistency  # STRONG / BOUNDED_STALENESS / EVENTUAL
    # Client/offline
    if re.search(r"\boffline[-\s]?first\b|\bbackground\s+sync\b", text, flags=re.I):
        derived["offline_support"] = True
    return derived
# ---------------------------------------------------------------------------


class Orchestrator:
    def __init__(self, policy: DecisionPolicy, agents: List[Any], logger: TraceLogger=None, facts: Optional[Dict[str, Any]]=None):
        self.policy = policy
        self.agents = agents
        self.logger = logger or TraceLogger()
        self.decision_id = None
        self.context: Dict[str, Any] = {"user_answers": {}, "derived": {}}
        self.facts = facts or {}  # optional seed facts

    def _merge_uncertainty(self, state: DebateState, updates: List[Dict[str, float]]):
        u_before = dict(state.uncertainty)
        u = dict(state.uncertainty)
        for upd in updates:
            for k, v in upd.items():
                u[k] = max(0.0, min(1.0, u.get(k, 0.0) + v))
        state.uncertainty = u
        self.logger.log_uncertainty(self.decision_id, u_before, state.uncertainty)

    # Heuristic to update uncertainty after answers (now also uses derived fields)
    def _ingest_answers(self, answers: Dict[str, str], state: DebateState) -> None:
        text = " ".join((answers or {}).values()).lower()
        deltas: Dict[str, float] = {}

        def decr(key: str, amt: float):
            deltas[key] = deltas.get(key, 0.0) - amt

        # keyword-based reductions (fallback)
        if any(k in text for k in ["rto", "rpo", "backup", "dr"]):
            decr("workload", 0.07)
        if any(k in text for k in ["gdpr", "hipaa", "pci", "residency", "region"]):
            decr("compliance", 0.10)
        if any(k in text for k in ["rps", "qps", "traffic", "throughput", "latency", "p95", "p99"]):
            decr("workload", 0.07); decr("latency", 0.05)
        if any(k in text for k in ["consistency", "strong", "eventual", "staleness"]):
            decr("data_quality", 0.07)
        if any(k in text for k in ["user", "sla", "ux", "offline", "mobile"]):
            decr("user_journeys", 0.06)
        if any(k in text for k in ["scope", "mvp", "out-of-scope", "phase"]):
            decr("scope", 0.05)

        # derived-based reductions (stronger signal)
        derived = _derive_from_answers(answers or {})
        if "RTO_s" in derived or "RPO_s" in derived:
            decr("workload", 0.05)
        if "residency" in derived:
            decr("compliance", 0.07)
        if "peak_rps" in derived or "p95_latency_ms" in derived:
            decr("workload", 0.05)
        if "consistency" in derived:
            decr("data_quality", 0.05)
        if derived.get("offline_support"):
            decr("user_journeys", 0.05)

        self._merge_uncertainty(state, [deltas])

    def _collect_scorecards(self, brief: ProblemBrief, state: DebateState) -> tuple[List[Scorecard], List[Tuple[str,float]]]:
        # Round 0
        sg: Scorecard = self.agents[0].analyze(brief, {}, context=self.context, facts=self.facts)
        self.logger.log_agent_card(self.decision_id, sg.agent, sg.__dict__)
        state.risk_mean = sg.risk_score
        state.risk_max = sg.risk_score
        self._merge_uncertainty(state, [sg.uncertainty_updates])

        all_cards = [sg]

        # Round 1
        for agent in self.agents[1:]:
            sc: Scorecard = agent.analyze(brief, {}, context=self.context, facts=self.facts)
            self.logger.log_agent_card(self.decision_id, sc.agent, sc.__dict__)
            all_cards.append(sc)
            state.risk_mean = (state.risk_mean + sc.risk_score) / 2.0
            state.risk_max = max(state.risk_max, sc.risk_score)
            self._merge_uncertainty(state, [sc.uncertainty_updates])

        ranked_qs: List[Tuple[str, float]] = []
        ranked_payload = []
        for sc in all_cards:
            for qc in sc.question_candidates:
                ig = abs(qc.get("expected_delta_risk", 0.0)) + sum(abs(v) for v in qc.get("expected_delta_U", {}).values())
                ranked_qs.append((qc["q"], ig))
                ranked_payload.append({
                    "q": qc.get("q",""),
                    "ig": ig,
                    "delta_U": qc.get("expected_delta_U",{}),
                    "delta_risk": qc.get("expected_delta_risk",0.0),
                    "agent": sc.agent
                })
        ranked_qs.sort(key=lambda x: x[1], reverse=True)
        ranked_payload.sort(key=lambda x: x["ig"], reverse=True)
        self.logger.log_question_ranking(self.decision_id, ranked_payload)
        return all_cards, ranked_qs

    def _compose_design(self, all_cards: List[Scorecard], ranked_qs: List[Tuple[str,float]], decision: DecisionOutput):
        containers = [
            {"name":"api-gateway","responsibility":"routing, authN","protocols":["https"]},
            {"name":"svc-core","responsibility":"business logic","protocols":["grpc","events"]},
            {"name":"db-primary","responsibility":"transactional store","type":"postgres"},
            {"name":"event-bus","responsibility":"async workflows","type":"kafka-like"},
            {"name":"worker","responsibility":"async jobs, saga orchestrations"}
        ]
        for sc in all_cards:
            for d in sc.design_deltas:
                containers.append({"name": f"delta::{d.get('change','')}", "responsibility": d.get("impact",""), "protocols": []})
        decision.c4_containers = containers
        decision.adrs = [
            {"id":"ADR-001", "title":"Async orchestration with Saga", "status":"proposed"},
            {"id":"ADR-002", "title":"Outbox pattern for writes", "status":"proposed"},
            {"id":"ADR-003", "title":"Tokenization for sensitive data", "status":"proposed"}
        ]
        decision.non_functionals = {"SLO_p99_ms": 1000, "RTO_hours": 2, "RPO_minutes": 15}
        decision.risks = ["Capacity assumptions may be low", "Compliance scope uncertain"]
        decision.open_questions = [q for q,_ in ranked_qs[:3]]
        self.logger.log_design_artifacts(self.decision_id, decision.c4_containers, decision.adrs)

    def _apply_answers_to_context_and_brief(self, brief: ProblemBrief, answers: Dict[str, str]) -> None:
        # 1) save raw answers
        self.context.setdefault("user_answers", {}).update(answers or {})

        # 2) derive structured hints
        derived = _derive_from_answers(answers or {})
        self.context.setdefault("derived", {}).update(derived)

        # 3) reflect into the brief constraints so agents see it even without context
        brief.constraints = {**brief.constraints, **{k: v for k, v in derived.items() if v is not None}}

        # 4) persist to facts (so future runs benefit)
        if isinstance(self.facts, dict):
            for k, v in derived.items():
                if v is not None:
                    self.facts[k] = v

    def run(self, brief: ProblemBrief, ask_callback: Optional[AskCallback]=None, auto_continue: bool=True, max_ask_loops: int=1) -> DecisionOutput:
        self.decision_id = self.logger.start_decision(brief.__dict__)
        state = DebateState()

        # First pass
        all_cards, ranked_qs = self._collect_scorecards(brief, state)
        decision = self.policy.decide(state, ranked_qs)
        # Defensive: ensure edr/ig_star fields exist even on old models.py
        if not hasattr(decision, "edr"):
            decision.edr = self.policy.compute_edr(state)
        if not hasattr(decision, "ig_star"):
            decision.ig_star = ranked_qs[0][1] if ranked_qs else 0.0
        self.logger.log_policy_decision(self.decision_id, decision.route, decision.reason, decision.edr, decision.ig_star)

        # ASK flow: optionally ask user, ingest answers, and re-decide
        loops = 0
        while decision.route == "ASK" and ask_callback and auto_continue and loops < max_ask_loops:
            qs = decision.questions
            answers = ask_callback(qs) or {}
            qa_list = [{"q": q, "a": answers.get(q, "")} for q in qs]
            self.logger.log_user_answers(self.decision_id, qa_list)

            # persist answers and mirror into brief
            self._apply_answers_to_context_and_brief(brief, answers)

            # reduce uncertainty using answers/derived
            self._ingest_answers(answers, state)

            # re-run agents with updated context
            all_cards, ranked_qs = self._collect_scorecards(brief, state)
            decision = self.policy.decide(state, ranked_qs)
            if not hasattr(decision, "edr"):
                decision.edr = self.policy.compute_edr(state)
            if not hasattr(decision, "ig_star"):
                decision.ig_star = ranked_qs[0][1] if ranked_qs else 0.0
            self.logger.log_policy_decision(self.decision_id, decision.route, decision.reason, decision.edr, decision.ig_star)
            loops += 1

        if decision.route == "DESIGN":
            self._compose_design(all_cards, ranked_qs, decision)

        self.logger.end_decision(self.decision_id)
        return decision
