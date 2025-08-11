from typing import Dict, Any, List
from .models import Scorecard, ProblemBrief

class AgentBase:
    name = "Base"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        raise NotImplementedError

# The following rule-based agents are lightweight stand-ins.
# In production, swap their logic with LLM-backed reasoning using your prompts.
def _kw(text: str, keys: List[str]) -> int:
    text_l = text.lower()
    return sum(1 for k in keys if k in text_l)

class SystemsGeneralistAgent(AgentBase):
    name = "SystemsGeneralist"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        # make a basic strawman if missing
        assumptions = ["Assume web/API workloads", "Assume single-digit k RPS unless stated"]
        concerns = []
        if _kw(brief.description, ["multi-region", "gdpr", "hipaa"]):
            concerns.append("Regulatory or residency implications suspected")
        strawman2 = strawman or {
            "containers": [
                {"name":"api-gateway", "responsibility":"routing, authN", "protocols":["https"]},
                {"name":"svc-core", "responsibility":"business logic", "protocols":["grpc","events"]},
                {"name":"db-primary", "responsibility":"transactional store", "type":"postgres"},
                {"name":"event-bus", "responsibility":"async workflows", "type":"kafka-like"},
                {"name":"worker", "responsibility":"async jobs, saga orchestrations"}
            ]
        }
        score = 0.35 if concerns else 0.25
        return Scorecard(
            agent=self.name,
            assumptions=assumptions,
            concerns=concerns,
            key_decisions=[
                {"topic":"sync vs async", "options":["sync","async+saga"], "recommend":"async+saga", "rationale":"increase resilience"}
            ],
            question_candidates=[
                {"q":"What are peak and diurnal RPS on the critical path?", "expected_delta_U":{"workload":-0.10}, "expected_delta_risk":-0.05},
                {"q":"Any explicit data residency/compliance constraints (HIPAA/GDPR/PCI)?", "expected_delta_U":{"compliance":-0.10}, "expected_delta_risk":-0.07}
            ],
            design_deltas=[],
            risk_score=score,
            uncertainty_updates={"scope": +0.05 if concerns else -0.05}
        )

class InfraReliabilityAgent(AgentBase):
    name = "InfraReliability"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        assumptions = ["Target SLO: p99 < 1s on critical APIs", "Multi-AZ base, backups daily"]
        concerns = []
        if _kw(brief.description, ["real-time", "latency"]):
            concerns.append("Aggressive latency budget suspected")
        questions = [{"q":"Required RTO/RPO?", "expected_delta_U":{"workload":-0.05}, "expected_delta_risk":-0.07}]
        deltas = [{"change":"Introduce outbox pattern on write paths", "impact":"+reliability +operability", "cost":"+2w"}]
        r = 0.4 if concerns else 0.3
        return Scorecard(self.name, assumptions, concerns, [], [], questions, deltas, r, {"workload": +0.05})

class DataIntegrationAgent(AgentBase):
    name = "DataIntegration"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        assumptions = ["Event-first contracts for cross-service flows", "Idempotency on writes"]
        concerns = []
        if _kw(brief.description, ["exactly-once", "ledger", "payments"]):
            concerns.append("Consistency semantics critical")
        questions = [{"q":"What consistency model is required (eventual, bounded-staleness, strong)?", "expected_delta_U":{"data_quality":-0.07}, "expected_delta_risk":-0.05}]
        deltas = [{"change":"Add idempotency keys & retry policies to write APIs", "impact":"+correctness", "cost":"+1w"}]
        r = 0.45 if concerns else 0.3
        return Scorecard(self.name, assumptions, concerns, [], [], questions, deltas, r, {"data_quality": +0.05})

class SecurityComplianceAgent(AgentBase):
    name = "SecurityCompliance"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        assumptions = ["OIDC + SCIM for identity, least privilege access", "At-rest & in-transit encryption"]
        concerns = []
        if _kw(brief.description, ["pii","phi","pci","health","payments","gdpr","hipaa"]):
            concerns.append("Sensitive data or regulated workload suspected")
        questions = [{"q":"What data classes are processed (PII/PHI/PCI)? Any regional residency rules?", "expected_delta_U":{"compliance":-0.12}, "expected_delta_risk":-0.08}]
        deltas = [{"change":"Adopt tokenization for sensitive fields", "impact":"+security, -blast radius", "cost":"+1w"}]
        r = 0.5 if concerns else 0.25
        return Scorecard(self.name, assumptions, concerns, [], [], questions, deltas, r, {"compliance": +0.08})

class FrontendMobileAgent(AgentBase):
    name = "FrontendMobile"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        assumptions = ["Explicit error-state design, retries with backoff", "Perf budgets on client"]
        questions = [{"q":"Do clients require offline-first or background sync?", "expected_delta_U":{"user_journeys":-0.06}, "expected_delta_risk":-0.03}]
        deltas = [{"change":"Add API pagination + caching hints", "impact":"+perf", "cost":"+0.5w"}]
        return Scorecard(self.name, assumptions, [], [], [], questions, deltas, 0.25, {"latency": +0.03})

class DomainAgent(AgentBase):
    name = "Domain"
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        assumptions = ["Domain KPIs defined with product"]
        questions = [{"q":"What are user-visible SLAs (e.g., payment confirmation time, error tolerance)?", "expected_delta_U":{"scope":-0.05, "domain_edge_cases":-0.08}, "expected_delta_risk":-0.04}]
        deltas = []
        return Scorecard(self.name, assumptions, [], [], [], questions, deltas, 0.3, {"domain_edge_cases": +0.05})
