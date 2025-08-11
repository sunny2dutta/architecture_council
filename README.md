# Architecture Council (Ask-or-Design) — Minimal Reference

This is a minimal, dependency-light Python reference for a **skills-based multi-agent architecture council**. 
It takes a problem brief, each agent produces a scorecard, we compute **Expected Design Risk (EDR)**, 
and choose between **ASK** (top questions) or **DESIGN** (C4-ish proposal + ADRs).

> ⚠️ In this demo, agents are **rule-based** (no external LLM calls) so it runs anywhere. 
Swap each agent's logic with your LLM prompts when you wire it into your stack.

## Quick start

```bash
python example.py

