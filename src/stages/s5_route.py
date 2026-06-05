import json
import os
import sys

from src.utils.state import PipelineState, OUTPUTS_DIR


def run_stage(
    state: PipelineState,
    tickets: list,
    draft_replies: list,
    policy_checks: list,
    llm_reviews: list,
    repaired_replies: list,
    overrides: list
) -> tuple[PipelineState, list]:
    """
    Stage 5: Final Routing.
    Calculates final route logic from deterministic outputs and human overrides.
    """
    if state != PipelineState.HUMAN_OVERRIDE_COMPLETE:
        print(
            f"[PIPELINE ERROR] Stage: final_routing, Ticket: None, "
            f"Error: Expected HUMAN_OVERRIDE_COMPLETE, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)

    # Fast Lookups
    checks_by_id = {pc["ticket_id"]: pc for pc in policy_checks}
    reviews_by_id = {lr["ticket_id"]: lr for lr in llm_reviews}
    repaired_by_id = {r["ticket_id"]: r for r in repaired_replies}
    overrides_by_id = {o["ticket_id"]: o["human_override_route"] for o in overrides}
    drafts_by_id = {d["ticket_id"]: d for d in draft_replies}
    
    final_decisions = []
    
    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        
        pc = checks_by_id[ticket_id]
        lr = reviews_by_id.get(ticket_id, {})
        
        # 1. Compute initial_route
        if not pc["passed"]:
            initial_route = "human_review"
            base_reason = f"deterministic checks failed ({', '.join(pc['failed_checks'])})"
        elif ticket.get("customer_tone") == "angry":
            initial_route = "human_review"
            base_reason = "customer_tone is angry"
        elif ticket.get("issue_type") == "bonus_dispute":
            initial_route = "human_review"
            base_reason = "issue_type is bonus_dispute"
        else:
            initial_route = "auto_send"
            q_rating = lr.get("quality_rating", "N/A")
            p_risk = lr.get("policy_risk", "N/A")
            base_reason = f"passed all deterministic checks, quality rating {q_rating}, policy risk {p_risk}"
            
        # 2. Apply Overrides
        was_overridden = ticket_id in overrides_by_id
        if was_overridden:
            final_route = overrides_by_id[ticket_id]
        else:
            final_route = initial_route
            
        # 3. Determine Final Draft Reply
        if ticket_id in repaired_by_id:
            final_reply_text = repaired_by_id[ticket_id]["repaired_reply_text"]
            is_repaired = True
        else:
            final_reply_text = drafts_by_id[ticket_id]["reply_text"]
            is_repaired = False
            
        # 4. Build Decision Reason
        if final_route == "auto_send":
            prefix = "Auto-send:"
        else:
            prefix = "Human review required:"
            
        decision_reason = f"{prefix} {base_reason}."
        
        if was_overridden:
            decision_reason += " Operator override applied."
        elif initial_route == "human_review":
            decision_reason += " No operator override."
            
        final_decisions.append({
            "ticket_id": ticket_id,
            "final_route": final_route,
            "is_repaired": is_repaired,
            "decision_reason": decision_reason,
            "final_draft_reply": final_reply_text
        })
        
        print(f"  [Stage 5] Routed {ticket_id}: {final_route}")

    # Write output
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "final_decisions.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_decisions, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: final_routing, Ticket: None, Error: Failed to write final_decisions.json: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.FINAL_ROUTING_DECIDED, final_decisions
