import os, time, re, sys
from council.models import ProblemBrief
from council.policy import DecisionPolicy
from council.orchestrator import Orchestrator
from council.logging_ext import TraceLogger
from council.llm import DeepSeekClient
from council.agents_llm import (
    LLMSystemsGeneralist, LLMInfraReliability, LLMDataIntegration,
    LLMSecurityCompliance, LLMFrontendMobile, LLMGameDomain
)

def require_env(var):
    val = os.getenv(var)
    if not val:
        print(f"Missing env var: {var}", file=sys.stderr)
        print("Set DEEPSEEK_API_BASE, DEEPSEEK_API_KEY, DEEPSEEK_MODEL before running.", file=sys.stderr)
        sys.exit(1)
    return val

def main():
    # Safety: ensure required env is set
    require_env("DEEPSEEK_API_BASE")
    require_env("DEEPSEEK_API_KEY")
    require_env("DEEPSEEK_MODEL")

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

    # Build DeepSeek client and LLM-backed agents
    client = DeepSeekClient()  # reads env: DEEPSEEK_API_BASE, DEEPSEEK_API_KEY, DEEPSEEK_MODEL
    agents = [
        LLMSystemsGeneralist(client),
        LLMInfraReliability(client),
        LLMDataIntegration(client),
        LLMSecurityCompliance(client),
        LLMFrontendMobile(client),
        LLMGameDomain(client),
    ]

    policy = DecisionPolicy()
    logger = TraceLogger(path="logs/decision_traces.jsonl")
    orch = Orchestrator(policy, agents, logger)

    start = time.time()
    decision = orch.run(brief)
    latency_ms = int((time.time() - start) * 1000)

    # Print summary
    print("\n=== Decision ===")
    print(decision.route, "-", decision.reason)
    if decision.route == "ASK":
        for i, q in enumerate(decision.questions, 1):
            print(f"{i}) {q}")
    else:
        print("C4 Containers:")
        for c in decision.c4_containers:
            print(" -", c)

    print(f"Latency: {latency_ms} ms")
    print("Trace log -> logs/decision_traces.jsonl")

if __name__ == "__main__":
    main()

