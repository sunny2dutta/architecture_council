
from typing import List, Dict, Any, Tuple
from .models import ProblemBrief, DebateState, DecisionOutput, Scorecard
from .policy import DecisionPolicy
from .logging_ext import TraceLogger

class Orchestrator:
    def __init__(self, policy: DecisionPolicy, agents: List[Any], logger: TraceLogger=None):
        self.policy = policy
        self.agents = agents
        self.logger = logger or TraceLogger()

    def _merge_uncertainty(self, state: DebateState, updates: List[Dict[str, float]]):
        u_before = dict(state.uncertainty)
        u = dict(state.uncertainty)
        for upd in updates:
            for k, v in upd.items():
                u[k] = max(0.0, min(1.0, u.get(k, 0.0) + v))
        state.uncertainty = u
        self.logger.log_uncertainty(self.decision_id, u_before, state.uncertainty)

    def run(self, brief: ProblemBrief, max_rounds: int = 2) -> DecisionOutput:
        self.decision_id = self.logger.start_decision(brief.__dict__)
        state = DebateState()

        # Round 0: first agent acts as Systems Generalist in your list
        sg: Scorecard = self.agents[0].analyze(brief, {})
        self.logger.log_agent_card(self.decision_id, sg.agent, sg.__dict__)
        state.risk_mean = sg.risk_score
        state.risk_max = sg.risk_score
        self._merge_uncertainty(state, [sg.uncertainty_updates])

        all_cards = [sg]

        # Round 1: remaining agents
        for agent in self.agents[1:]:
            sc: Scorecard = agent.analyze(brief, {})
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
                ranked_payload.append({"q": qc.get("q",""), "ig": ig, "delta_U": qc.get("expected_delta_U",{}), "delta_risk": qc.get("expected_delta_risk",0.0), "agent": sc.agent})
        ranked_qs.sort(key=lambda x: x[1], reverse=True)
        ranked_payload.sort(key=lambda x: x["ig"], reverse=True)
        self.logger.log_question_ranking(self.decision_id, ranked_payload)

        decision = self.policy.decide(state, ranked_qs)
        self.logger.log_policy_decision(self.decision_id, decision.route, decision.reason, decision.edr, decision.ig_star)

        if decision.route == "DESIGN":
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

        self.logger.end_decision(self.decision_id)
        return decision
