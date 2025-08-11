import json, time, os, re
from council.models import ProblemBrief
from council.policy import DecisionPolicy
from council.orchestrator import Orchestrator
from council.eval import Evaluator

def main():
    brief = ProblemBrief(
        title="Subscriptions Payments Service",
        description=(
            "Design a payments microservice for subscriptions across US/EU with GDPR. "
            "We need near real-time confirmation, ledger accuracy, and resiliency. "
            "Traffic expected to grow. Consider PCI/PII implications."
        ),
        constraints={"deadline_weeks": 8},
        must_haves=["idempotency", "async workflows"],
        metrics=["auth_success_rate", "p95_latency_ms"],
        timelines={"MVP": "8w"},
        known_risks=["chargeback flow complexity"],
        unknowns=["PCI scope", "regional data residency"]
    )

    # Policy with default weights
    policy = DecisionPolicy()
    orch = Orchestrator(policy)

    start = time.time()
    decision = orch.run(brief)
    latency_ms = int((time.time() - start) * 1000)

    # Evaluator / telemetry setup
    os.makedirs("telemetry", exist_ok=True)
    ev = Evaluator(db_path="telemetry/council.db", weights_path="telemetry/weights.json")

    # Extract EDR and IG* from decision.reason (in production, pass explicitly)
    m = re.search(r'EDR=(\d+\.\d+)', decision.reason)
    edr_num = float(m.group(1)) if m else 0.5
    m2 = re.search(r'IG\*=(\d+\.\d+)', decision.reason)
    ig_star = float(m2.group(1)) if m2 else 0.0

    # Log decision and questions if ASK
    did = ev.log_decision(
        brief.title, decision.route, decision.reason,
        edr_num, ig_star, telemetry={"latency_ms": latency_ms}
    )
    if decision.route == "ASK":
        ev.log_questions(did, decision.questions, [1] * len(decision.questions))

    # Print output
    print("\n=== Decision ===")
    print(decision.route, "-", decision.reason)
    if decision.route == "ASK":
        for i, q in enumerate(decision.questions, 1):
            print(f"{i}) {q}")
    else:
        print("C4 Containers:")
        for c in decision.c4_containers:
            print(" -", c)

    # Example: later you can log actual outcomes (after deployment)
    # ev.log_outcome(did, rework=0, incidents=0, predictability=0.9, adopted=1)

if __name__ == "__main__":
    main()

