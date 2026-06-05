import json
import os
import re
import sys

from src.utils.state import PipelineState, OUTPUTS_DIR


def evaluate_reply(reply_text: str, ticket: dict, policy: dict) -> tuple[int, list, bool]:
    """
    Evaluates a single reply against the 5 deterministic rules.
    Returns: (score, failed_checks, passed)
    """
    failed_checks = []
    reply_lower = reply_text.lower()
    
    # 1. required_sections_present
    missing_sections = [
        s for s in policy.get("required_reply_sections", [])
        if s.lower().replace("_", " ") not in reply_lower and s.lower() not in reply_lower
    ]
    if missing_sections:
        failed_checks.append("required_sections_present")
        
    # 2. no_password_request
    if any(pw_phrase in reply_lower for pw_phrase in ["full password", "entire password", "complete password"]):
        failed_checks.append("no_password_request")
        
    # 3. no_guaranteed_timeline
    timeline_pattern = r"(?i)(will be resolved in|guaranteed by|approved within|released in \w+ (days|hours))"
    if re.search(timeline_pattern, reply_text):
        failed_checks.append("no_guaranteed_timeline")
        
    # 4. no_unsupported_funds_released
    account_context = ticket.get("account_context", {})
    withdrawal_status = account_context.get("withdrawal_status")
    if withdrawal_status != "released":
        funds_pattern = r"(?i)((funds|payment)\s+(are\s+|is\s+|have\s+been\s+|has\s+been\s+)?(released|sent)|(released|sent)\s+(your\s+)?(funds|payment|money))"
        if re.search(funds_pattern, reply_text):
            failed_checks.append("no_unsupported_funds_released")
            
    # 5. no_blaming_language
    blame_phrases = ["your fault", "you should have", "you didn't", "you failed"]
    if any(phrase in reply_lower for phrase in blame_phrases):
        failed_checks.append("no_blaming_language")
        
    # Compute deterministic_score
    score = 100
    if "required_sections_present" in failed_checks:
        score -= 30
    if "no_password_request" in failed_checks:
        score -= 25
    if "no_guaranteed_timeline" in failed_checks:
        score -= 20
    if "no_unsupported_funds_released" in failed_checks:
        score -= 15
    if "no_blaming_language" in failed_checks:
        score -= 10
        
    score = max(0, score)
    passed = (score == 100)
    
    return score, failed_checks, passed


def run_stage(
    state: PipelineState,
    tickets: list,
    policy: dict,
    draft_replies: list
) -> tuple[PipelineState, list]:
    """
    Stage 2: Deterministic Policy Checks.
    Evaluates each draft reply against 5 rule-based checks.
    """
    if state != PipelineState.DRAFT_REPLIES_GENERATED:
        print(
            f"[PIPELINE ERROR] Stage: check, Ticket: None, "
            f"Error: Expected state DRAFT_REPLIES_GENERATED, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)

    policy_checks = []
    tickets_by_id = {t["ticket_id"]: t for t in tickets}

    for draft in draft_replies:
        ticket_id = draft["ticket_id"]
        reply_text = draft["reply_text"]
        ticket = tickets_by_id[ticket_id]
        
        score, failed_checks, passed = evaluate_reply(reply_text, ticket, policy)
        
        must_human_review = (
            (not passed) or 
            (ticket.get("customer_tone") == "angry") or 
            (ticket.get("issue_type") == "bonus_dispute")
        )
        
        policy_checks.append({
            "ticket_id": ticket_id,
            "passed": passed,
            "failed_checks": failed_checks,
            "must_human_review": must_human_review,
            "deterministic_score": score
        })
        
        print(f"  [Stage 2] Evaluated {ticket_id}: score={score}, passed={passed}, must_review={must_human_review}")

    # Write outputs/policy_checks.json
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "policy_checks.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(policy_checks, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: check, Ticket: None, Error: Failed to write {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.DETERMINISTIC_CHECKS_COMPLETE, policy_checks
