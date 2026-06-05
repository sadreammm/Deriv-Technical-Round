import json
import os
import sys

from src.utils.state import PipelineState, GENERATION_MODEL, MAX_TOKENS, OUTPUTS_DIR
from src.llm.client import get_client, call_model
from src.stages.s2_check import evaluate_reply

_SYSTEM_PROMPT = (
    "You are a compliance repair agent. "
    "Your job is to fix a customer support reply that failed strict policy checks. "
    "You must maintain the original tone and intent, but alter the text to pass the failed checks."
)

_REPAIR_OUTPUT = "outputs/repaired_replies.json"
_INPUT_ARTIFACTS = ["tickets.json", "policy.json", "draft_replies.json", "policy_checks.json"]


def _build_repair_prompt(ticket: dict, original_reply: str, failed_checks: list, policy: dict) -> str:
    """
    Constructs the prompt telling the LLM exactly what checks failed and asking it to fix the text.
    """
    required_sections = ", ".join(policy.get("required_reply_sections", []))
    forbidden_claims = ", ".join(policy.get("forbidden_claims", []))
    
    prompt = (
        f"Ticket ID: {ticket['ticket_id']}\n"
        f"Original Reply:\n{original_reply}\n\n"
        f"This reply failed the following policy checks: {', '.join(failed_checks)}\n\n"
        f"Policy - Required sections: {required_sections}\n"
        f"Policy - Forbidden claims: {forbidden_claims}\n\n"
        f"Please rewrite the reply so that it passes the failed checks. "
        f"Ensure it still includes the required sections, does not ask for passwords, does not make guaranteed timeline promises, "
        f"does not claim funds are released if the status is not released, and does not use blaming language."
    )
    return prompt


def run_stage(
    state: PipelineState,
    tickets: list,
    policy: dict,
    draft_replies: list,
    policy_checks: list
) -> tuple[PipelineState, list]:
    """
    Stage 2b: Repair.
    Attempts to fix draft replies that failed deterministic checks.
    """
    if state != PipelineState.DETERMINISTIC_CHECKS_COMPLETE:
        print(
            f"[PIPELINE ERROR] Stage: repair, Ticket: None, "
            f"Error: Expected state DETERMINISTIC_CHECKS_COMPLETE, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)
        
    failed_policy_checks = [pc for pc in policy_checks if not pc["passed"]]
    
    if not failed_policy_checks:
        # If no tickets failed, write [] and return immediately
        os.makedirs(OUTPUTS_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUTS_DIR, "repaired_replies.json")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
        except Exception as e:
            print(f"[PIPELINE ERROR] Stage: repair, Ticket: None, Error: Failed to write {_REPAIR_OUTPUT}: {e}", file=sys.stderr)
            sys.exit(1)
            
        print("  [Stage 2b] No tickets failed deterministic checks. Skipping repair.")
        return PipelineState.DETERMINISTIC_CHECKS_COMPLETE, []

    client = get_client()
    tickets_by_id = {t["ticket_id"]: t for t in tickets}
    drafts_by_id = {d["ticket_id"]: d for d in draft_replies}
    
    repaired_replies = []
    
    for failed_pc in failed_policy_checks:
        ticket_id = failed_pc["ticket_id"]
        failed_checks_list = failed_pc["failed_checks"]
        
        ticket = tickets_by_id[ticket_id]
        original_reply = drafts_by_id[ticket_id]["reply_text"]
        
        prompt = _build_repair_prompt(ticket, original_reply, failed_checks_list, policy)
        
        # Call LLM to attempt a repair
        repaired_reply_text = call_model(
            client=client,
            model=GENERATION_MODEL,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
            stage="repair",
            ticket_id=ticket_id,
            input_artifacts=_INPUT_ARTIFACTS,
            output_artifact=_REPAIR_OUTPUT,
        )
        
        # Re-evaluate the repaired text using the exact same checks
        score, new_failed_checks, passed = evaluate_reply(repaired_reply_text, ticket, policy)
        
        # Compute resolved and still failed
        repair_resolved_checks = [c for c in failed_checks_list if c not in new_failed_checks]
        still_failed_checks = [c for c in failed_checks_list if c in new_failed_checks]
        
        repaired_replies.append({
            "ticket_id": ticket_id,
            "repaired_reply_text": repaired_reply_text,
            "repair_resolved_checks": repair_resolved_checks,
            "still_failed_checks": still_failed_checks
        })
        
        print(f"  [Stage 2b] Repaired {ticket_id}: resolved {len(repair_resolved_checks)}, still failed {len(still_failed_checks)}")

    # Safely write the outputs to repaired_replies.json
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "repaired_replies.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(repaired_replies, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: repair, Ticket: None, Error: Failed to write {_REPAIR_OUTPUT}: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.DETERMINISTIC_CHECKS_COMPLETE, repaired_replies
