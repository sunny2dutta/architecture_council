from typing import List, Dict, Any, Tuple
from .models import ProblemBrief, DebateState, DecisionOutput
from .agents import (
    SystemsGeneralistAgent, InfraReliabilityAgent, DataIntegrationAgent,
    SecurityComplianceAgent, FrontendMobileAgent, DomainAgent, AgentBase
)
from .policy import DecisionPolicy

class Orchestrator:
    def __init__(self, policy: DecisionPolicy):
        self.policy = policy
        self.agents: List[AgentBase] = [
            SystemsGeneralistAgent(), InfraReliabilityAgent(), DataIntegrationAgent(),
            SecurityComplianceAgent(), FrontendMobileAgent(), DomainAgent()
        ]

    def _merge_uncertainty(self, state: DebateState, updates: List[Dict[str, float]]):
        u = dict(state.uncertainty)
        for upd in updates:
            for k, v in upd.items():
                u[k] = max(0.0, min(1.0, u.get(k, 0.0) + v))
        state.uncertainty = u

    def run(self, brief: ProblemBrief, max_rounds: int = 2) -> DecisionOutput:
        state = DebateState()
        strawman = {}
        # Round 0: Systems Generalist framing (must run first)
        sg = self.agents[0].analyze(brief, strawman)
        strawman = {"containers":[c for c in sg.assumptions if False]}  # keep type, but unused
        # Actually use SG default strawman by re-running with empty strawman
        sg = self.agents[0].analyze(brief, {})
        merged = {"strawman": sg}
        state.risk_mean = sg.risk_score
        state.risk_max = sg.risk_score
        self._merge_uncertainty(state, [sg.uncertainty_updates])

        all_cards = [sg]
        # Round 1: parallel agents
        for a in self.agents[1:]:
            sc = a.analyze(brief, merged.get("strawman", {}))
            all_cards.append(sc)
            state.risk_mean = (state.risk_mean + sc.risk_score) / 2.0
            state.risk_max = max(state.risk_max, sc.risk_score)
            self._merge_uncertainty(state, [sc.uncertainty_updates])

        # Rank questions by naive expected info gain = |delta_risk| + sum(|delta_U|)
        ranked_qs: List[Tuple[str, float]] = []
        for sc in all_cards:
            for qc in sc.question_candidates:
                ig = abs(qc.get("expected_delta_risk", 0.0)) + sum(abs(v) for v in qc.get("expected_delta_U", {}).values())
                ranked_qs.append((qc["q"], ig))
        ranked_qs.sort(key=lambda x: x[1], reverse=True)

        # Decide Ask vs Design
        decision = self.policy.decide(state, ranked_qs)

        if decision.route == "DESIGN":
            # Compose a simple design from agents' deltas + SG strawman
            containers = [
                {"name":"api-gateway","responsibility":"routing, authN","protocols":["https"]},
                {"name":"svc-core","responsibility":"business logic","protocols":["grpc","events"]},
                {"name":"db-primary","responsibility":"transactional store","type":"postgres"},
                {"name":"event-bus","responsibility":"async workflows","type":"kafka-like"},
                {"name":"worker","responsibility":"async jobs, saga orchestrations"}
            ]
            for sc in all_cards:
                for d in sc.design_deltas:
                    containers.append({"name": f"delta::{d['change']}", "responsibility": d.get("impact",""), "protocols": []})
            decision.c4_containers = containers
            decision.adrs = [
                {"id":"ADR-001", "title":"Async orchestration with Saga", "status":"proposed"},
                {"id":"ADR-002", "title":"Outbox pattern for writes", "status":"proposed"},
                {"id":"ADR-003", "title":"Tokenization for sensitive data", "status":"proposed"}
            ]
            decision.non_functionals = {"SLO_p99_ms": 1000, "RTO_hours": 2, "RPO_minutes": 15}
            decision.risks = ["Capacity assumptions may be low", "Compliance scope uncertain"]
            decision.open_questions = [q for q,_ in ranked_qs[:3]]
        return decision
