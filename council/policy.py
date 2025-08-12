from typing import Dict, List, Tuple
from .models import DebateState, DecisionOutput

class DecisionPolicy:
    """Ask vs Design policy with learnable weights for EDR (expected design risk)."""
    def __init__(self, weights: Dict[str, float] = None, ask_threshold: float = 0.55, ig_threshold: float = 0.15):
        # weight keys must match uncertainty dims and 'risk_mean'
        default = {
            "risk_mean": 0.35,
            "scope": 0.25,
            "domain_edge_cases": 0.25,  # folded inside computation as max(scope, domain_edge_cases)
            "workload": 0.15,
            "compliance": 0.10,
            "data_quality": 0.10,
            "third_party": 0.05
        }
        self.weights = weights or default
        self.ask_threshold = ask_threshold
        self.ig_threshold = ig_threshold

    def compute_edr(self, state: DebateState) -> float:
        w = self.weights
        # emulate the described formula, clamp between 0..1
        scope_like = max(state.uncertainty.get("scope", 0), state.uncertainty.get("domain_edge_cases", 0))
        edr = (
            w.get("risk_mean", 0.35) * state.risk_mean +
            w.get("scope", 0.25) * scope_like +
            w.get("workload", 0.15) * state.uncertainty.get("workload", 0) +
            w.get("compliance", 0.10) * state.uncertainty.get("compliance", 0) +
            w.get("data_quality", 0.10) * state.uncertainty.get("data_quality", 0) +
            w.get("third_party", 0.05) * state.uncertainty.get("third_party", 0)
        )
        return max(0.0, min(1.0, edr))

    def decide(self, state: DebateState, ranked_questions):
        edr = self.compute_edr(state)
        ig_star = ranked_questions[0][1] if ranked_questions else 0.0

        if edr > self.ask_threshold and ig_star >= self.ig_threshold:
            top_qs = [q for q, _ in ranked_questions[:3]]
            return DecisionOutput(
                route="ASK",
                reason=f"EDR={edr:.2f}, IG*={ig_star:.2f} -> Ask for high information gain",
                questions=top_qs,
                edr=edr,
                ig_star=ig_star,
            )
        else:
            return DecisionOutput(
                route="DESIGN",
                reason=f"EDR={edr:.2f}, IG*={ig_star:.2f} -> Confident enough to propose a design",
                edr=edr,
                ig_star=ig_star,
            )


    def ask_user_cli(questions: list[str]) -> dict[str, str]:
        if not questions:
            print("[ASK] (no questions)")
            return {}
        print("\n[ASK] I need a few clarifications:")
        answers = {}
        for q in questions:
            print(f"- {q}")
            try:
                a = input("  your answer: ").strip()
            except EOFError:
                print("  (stdin not available; leaving blank)")
                a = ""
            answers[q] = a
        return answers
