from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Scorecard:
    agent: str
    assumptions: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    key_decisions: List[Dict[str, Any]] = field(default_factory=list)
    question_candidates: List[Dict[str, Any]] = field(default_factory=list)  # each: {q, expected_delta_U, expected_delta_risk}
    design_deltas: List[Dict[str, Any]] = field(default_factory=list)        # each: {change, impact, cost}
    risk_score: float = 0.0
    uncertainty_updates: Dict[str, float] = field(default_factory=dict)

@dataclass
class DecisionOutput:
    route: str  # 'ASK' or 'DESIGN'
    reason: str
    questions: List[str] = field(default_factory=list)  # when ASK
    c4_containers: List[Dict[str, Any]] = field(default_factory=list)  # when DESIGN
    adrs: List[Dict[str, Any]] = field(default_factory=list)          # when DESIGN
    non_functionals: Dict[str, Any] = field(default_factory=dict)     # when DESIGN
    risks: List[str] = field(default_factory=list)                     # when DESIGN
    open_questions: List[str] = field(default_factory=list)            # when DESIGN

@dataclass
class ProblemBrief:
    title: str
    description: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    must_haves: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    timelines: Dict[str, Any] = field(default_factory=dict)
    known_risks: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)

@dataclass
class DebateState:
    strawman: Dict[str, Any] = field(default_factory=dict)
    uncertainty: Dict[str, float] = field(default_factory=lambda: {
        "scope": 0.4, "workload": 0.4, "compliance": 0.3, "data_quality": 0.3,
        "latency": 0.3, "cost": 0.3, "user_journeys": 0.3, "third_party": 0.3, "domain_edge_cases": 0.4
    })
    risk_mean: float = 0.0
    risk_max: float = 0.0
    merged: Dict[str, Any] = field(default_factory=dict)
