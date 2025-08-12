import os, time, sys
from typing import Any, Dict

from council.models import ProblemBrief
from council.policy import DecisionPolicy
from council.orchestrator import Orchestrator
from council.logging_ext import TraceLogger
from council.llm import DeepSeekClient

from council.agents import create_default_agents
from council.agents.base import parse_json_safely

import json

def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        print(f"Missing env var: {var}", file=sys.stderr)
        print("Set DEEPSEEK_API_BASE, DEEPSEEK_API_KEY, DEEPSEEK_MODEL before running.", file=sys.stderr)
        sys.exit(1)
    return val

def ask_user_cli(questions: list[str]) -> dict[str, str]:
    print("\nI need a few clarifications:")
    answers: Dict[str, str] = {}
    for q in questions:
        print(f"- {q}")
        try:
            a = input("  your answer: ").strip()
        except EOFError:
            a = ""
        answers[q] = a
    return answers

PARSE_BRIEF_PROMPT = """
You are a software architecture assistant. Your job is to read a freeform project description
and extract a structured ProblemBrief object.

Expected JSON format:
{
  "title": "string",
  "description": "string",
  "constraints": { "k": "v" },
  "must_haves": ["string"],
  "metrics": ["string"],
  "timelines": { "k": "v" },
  "known_risks": ["string"],
  "unknowns": ["string"]
}

Rules:
- Keep 'title' short (max 8 words).
- 'description' should summarize the project in 2–3 sentences.
- Fill 'constraints' only with hard deadlines, budgets, compliance requirements, etc.
- If not mentioned, leave an empty list or dict, not null.
- Do NOT include chain-of-thought. Return JSON only.
"""

def parse_paragraph_to_brief(client: DeepSeekClient, paragraph: str) -> ProblemBrief:
    messages = [
        {"role": "system", "content": PARSE_BRIEF_PROMPT},
        {"role": "user", "content": paragraph}
    ]
    out = client.chat(messages, max_tokens=7000, extra={"stream": False})
    obj = parse_json_safely(out["content"]) or {}
    return ProblemBrief(
        title=obj.get("title", ""),
        description=obj.get("description", ""),
        constraints=obj.get("constraints", {}),
        must_haves=obj.get("must_haves", []),
        metrics=obj.get("metrics", []),
        timelines=obj.get("timelines", {}),
        known_risks=obj.get("known_risks", []),
        unknowns=obj.get("unknowns", []),
    )

def main():
    # Ensure required env is set
    require_env("DEEPSEEK_API_BASE")
    require_env("DEEPSEEK_API_KEY")
    require_env("DEEPSEEK_MODEL")

    paragraph = "Design a system to detect spam in Instagram."

    # Build client and agents
    client = DeepSeekClient()
    agents = create_default_agents(client)  # Systems, Infra, Data, Security, Frontend, Domain, ML

    brief = parse_paragraph_to_brief(client, paragraph)
    print("Structured problem")
    print(brief)
    policy = DecisionPolicy()
    logger = TraceLogger(path="logs/decision_traces.jsonl")
    orch = Orchestrator(policy, agents, logger)

    start = time.time()
    decision = orch.run(brief, ask_callback=ask_user_cli, auto_continue=True, max_ask_loops=10)
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
