def _compose_design(self, all_cards, ranked_qs, decision):
    derived = self.context.get("derived", {})
    props = _normalize_proposals(all_cards)
    if not props:
        # no baseline fallback — reflect reality
        decision.c4_containers = []
        decision.adrs = []
        decision.non_functionals = {k: v for k, v in derived.items() if k in ("p95_latency_ms","peak_rps","RTO_s","RPO_s","residency","consistency")}
        decision.risks = list({c for sc in all_cards for c in (sc.concerns or [])})[:10]
        decision.open_questions = [q for q,_ in ranked_qs[:3]]
        decision.reason += " | No proposals from experts; emitting empty design."
        return

    clusters = _cluster(props, sim_th=0.5)
    chosen = []
    for cl in clusters:
        p, score = _score_cluster(cl, derived)
        chosen.append((p, score))
    chosen.sort(key=lambda x: x[1], reverse=True)

    # Design from winners ONLY (no baseline)
    decision.c4_containers = [{
        "name": f"{(p.get('category') or 'component')}::{p['name']}",
        "responsibility": p.get("impact") or p.get("change"),
        "meta": {"agent": p["agent"], "confidence": p.get("confidence"), "score": score}
    } for p, score in chosen]

    decision.adrs = [{
        "id": f"ADR-{100+i:03d}",
        "title": f"Adopt {p.get('change') or p.get('impact')}",
        "status": "proposed",
        "reason": f"score={score}, agent={p['agent']}, votes≈{sum(1 for _ in cl)}"
    } for i,(p,score) in enumerate(chosen,1) for cl in [[]]]  # simple placeholder for votes

    decision.non_functionals = {k: v for k, v in derived.items() if k in ("p95_latency_ms","peak_rps","RTO_s","RPO_s","residency","consistency")}
    decision.risks = list({c for sc in all_cards for c in (sc.concerns or [])})[:10]
    decision.open_questions = [q for q,_ in ranked_qs[:3]]

    self.logger.log_design_artifacts(self.decision_id, decision.c4_containers, decision.adrs)
