
import json
from typing import Dict, Any
from .models import Scorecard, ProblemBrief
from .llm import DeepSeekClient

SCHEMA_HINT = {
    "agent": "string",
    "assumptions": ["string"],
    "concerns": ["string"],
    "blockers": ["string"],
    "key_decisions": [{"topic":"string","options":["string"],"recommend":"string","rationale":"string"}],
    "question_candidates": [{"q":"string","expected_delta_U":{"k":"float"},"expected_delta_risk":"float"}],
    "design_deltas": [{"change":"string","impact":"string","cost":"string"}],
    "risk_score": 0.0,
    "uncertainty_updates": {"k":"float"},
    "rationale_summary": "short, <=50 words"
}

BASE_SYS = "You are an expert software architect. ONLY output valid JSON matching the provided schema; no prose."

def render_prompt(role: str, brief: ProblemBrief) -> str:
    template = """
Role: {role} architect.
Mission: Analyze the problem and return a Scorecard JSON.
Problem:
Title: {title}
Description: {description}
Constraints: {constraints}
Must-haves: {must_haves}
Metrics: {metrics}
Timelines: {timelines}
Known risks: {known_risks}
Unknowns: {unknowns}

Output JSON schema (example keys/types, not strings):
{json_schema}

Rules:
- risk_score ∈ [0,1]
- uncertainty_updates values ∈ [-1,1]
- question_candidates must include expected_delta_U (dict) and expected_delta_risk (float)
- rationale_summary ≤ 50 words
- Do NOT include any chain-of-thought; return the final JSON only.
"""
    return template.format(
        role=role,
        title=brief.title,
        description=brief.description,
        constraints=brief.constraints,
        must_haves=brief.must_haves,
        metrics=brief.metrics,
        timelines=brief.timelines,
        known_risks=brief.known_risks,
        unknowns=brief.unknowns,
        json_schema=json.dumps(SCHEMA_HINT, indent=2)
    )

def parse_json_safely(txt: str) -> Dict[str, Any]:
    # attempt to locate JSON
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # try to find first {...} block
        start = txt.find("{")
        end = txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(txt[start:end+1])
            except Exception:
                pass
    return {}

class LLMSystemsGeneralist:
    role = "Systems"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Systems Generalist", brief)}
        ]
        out = self.client.chat(messages)
        obj = parse_json_safely(out["content"]) or {}
        return Scorecard(**{
            "agent": "SystemsGeneralist",
            **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"}
        })

class LLMInfraReliability:
    role = "Infra/SRE"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Infra/SRE", brief)}
        ]
        obj = parse_json_safely(self.client.chat(messages)["content"])
        return Scorecard(agent="InfraReliability", **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"})

class LLMDataIntegration:
    role = "Data/Integration"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Data/Integration", brief)}
        ]
        obj = parse_json_safely(self.client.chat(messages)["content"])
        return Scorecard(agent="DataIntegration", **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"})

class LLMSecurityCompliance:
    role = "Security/Compliance"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Security/Compliance", brief)}
        ]
        obj = parse_json_safely(self.client.chat(messages)["content"])
        return Scorecard(agent="SecurityCompliance", **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"})

class LLMFrontendMobile:
    role = "Frontend/Mobile"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Frontend/Mobile", brief)}
        ]
        obj = parse_json_safely(self.client.chat(messages)["content"])
        return Scorecard(agent="FrontendMobile", **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"})

class LLMGameDomain:
    role = "Domain"
    def __init__(self, client: DeepSeekClient): self.client = client
    def analyze(self, brief: ProblemBrief, strawman: Dict[str, Any]) -> Scorecard:
        messages = [
            {"role":"system", "content": BASE_SYS},
            {"role":"user", "content": render_prompt("Domain", brief)}
        ]
        obj = parse_json_safely(self.client.chat(messages)["content"])
        return Scorecard(agent="Domain", **{k: obj.get(k, v) for k,v in Scorecard(agent="x").__dict__.items() if k != "agent"})
