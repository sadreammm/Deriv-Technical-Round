import json
import os
import re
import sys

from src.utils.state import PipelineState, REVIEW_MODEL, MAX_TOKENS, OUTPUTS_DIR
from src.llm.client import get_client, call_model

_SYSTEM_PROMPT = (
    "You are a Quality Assurance reviewer for customer support replies. "
    "Your task is to evaluate the reply text based on the provided ticket context, policy rules, and rubric. "
    "You must respond ONLY with a raw JSON object. Do not include markdown code fences, do not include any preamble, "
    "and do not include any postamble text."
)

_REVIEW_OUTPUT = "outputs/llm_review.json"
_INPUT_ARTIFACTS = ["tickets.json", "policy.json", "draft_replies.json", "policy_checks.json", "repaired_replies.json"]


def _build_review_prompt(ticket: dict, reply_text: str, policy: dict, policy_check: dict) -> str:
    """
    Constructs the prompt containing all context needed for the LLM to review the ticket.
    """
    prompt = (
        f"--- TICKET ---\n"
        f"{json.dumps(ticket, indent=2)}\n\n"
        f"--- REPLY TEXT TO REVIEW ---\n"
        f"{reply_text}\n\n"
        f"--- POLICY RULES ---\n"
        f"{json.dumps(policy, indent=2)}\n\n"
        f"--- POLICY CHECK RESULTS ---\n"
        f"{json.dumps(policy_check, indent=2)}\n\n"
        f"--- QUALITY RUBRIC ---\n"
        f"{json.dumps(policy.get('quality_rubric', {}), indent=2)}\n\n"
        f"Please provide your review in the following JSON format strictly:\n"
        f"{{\n"
        f"  \"quality_rating\": <integer from 1 to 5 based on the rubric>,\n"
        f"  \"policy_risk\": <string, exactly one of \"low\", \"medium\", or \"high\">,\n"
        f"  \"review_summary\": <string, brief justification of the rating>,\n"
        f"  \"suggested_fix\": <string, suggest how to improve it, or write \"None\" if perfect>\n"
        f"}}"
    )
    return prompt


def _strip_markdown_fences(text: str) -> str:
    """
    Removes ```json or ``` markdown code fences from the start/end of the text.
    """
    text = text.strip()
    # Remove leading ```json or ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove trailing ```
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def run_stage(
    state: PipelineState,
    tickets: list,
    policy: dict,
    draft_replies: list,
    policy_checks: list,
    repaired_replies: list
) -> tuple[PipelineState, list]:
    """
    Stage 3: LLM Review.
    Evaluates the final reply text (repaired if applicable, original otherwise) using the LLM reviewer model.
    """
    if state != PipelineState.DETERMINISTIC_CHECKS_COMPLETE:
        print(
            f"[PIPELINE ERROR] Stage: llm_review, Ticket: None, "
            f"Error: Expected state DETERMINISTIC_CHECKS_COMPLETE, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)

    client = get_client()
    
    # Fast lookups
    tickets_by_id = {t["ticket_id"]: t for t in tickets}
    drafts_by_id = {d["ticket_id"]: d for d in draft_replies}
    checks_by_id = {pc["ticket_id"]: pc for pc in policy_checks}
    repaired_by_id = {r["ticket_id"]: r for r in repaired_replies}
    
    llm_reviews = []
    
    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        
        # Determine which text to review: repaired if available, else original draft
        if ticket_id in repaired_by_id:
            reply_text = repaired_by_id[ticket_id]["repaired_reply_text"]
        else:
            reply_text = drafts_by_id[ticket_id]["reply_text"]
            
        policy_check = checks_by_id[ticket_id]
        
        prompt = _build_review_prompt(ticket, reply_text, policy, policy_check)
        
        # Call LLM Review model
        raw_response = call_model(
            client=client,
            model=REVIEW_MODEL,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
            stage="llm_review",
            ticket_id=ticket_id,
            input_artifacts=_INPUT_ARTIFACTS,
            output_artifact=_REVIEW_OUTPUT,
        )
        
        # Clean markdown if the LLM ignored instructions
        json_text = _strip_markdown_fences(raw_response)
        
        # Parse and Validate
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError as e:
            print(
                f"[PIPELINE ERROR] Stage: llm_review, Ticket: {ticket_id}, "
                f"Error: Failed to parse LLM response as JSON. Response: {raw_response}",
                file=sys.stderr
            )
            sys.exit(1)
            
        # Validation checks
        quality_rating = parsed.get("quality_rating")
        policy_risk = parsed.get("policy_risk")
        review_summary = parsed.get("review_summary")
        suggested_fix = parsed.get("suggested_fix")
        
        if not isinstance(quality_rating, int) or not (1 <= quality_rating <= 5):
            print(f"[PIPELINE ERROR] Stage: llm_review, Ticket: {ticket_id}, Error: Invalid quality_rating: {quality_rating}", file=sys.stderr)
            sys.exit(1)
            
        if policy_risk not in ["low", "medium", "high"]:
            print(f"[PIPELINE ERROR] Stage: llm_review, Ticket: {ticket_id}, Error: Invalid policy_risk: {policy_risk}", file=sys.stderr)
            sys.exit(1)
            
        if not isinstance(review_summary, str) or not review_summary.strip():
            print(f"[PIPELINE ERROR] Stage: llm_review, Ticket: {ticket_id}, Error: Invalid or missing review_summary", file=sys.stderr)
            sys.exit(1)
            
        if not isinstance(suggested_fix, str) or not suggested_fix.strip():
            print(f"[PIPELINE ERROR] Stage: llm_review, Ticket: {ticket_id}, Error: Invalid or missing suggested_fix", file=sys.stderr)
            sys.exit(1)
            
        llm_reviews.append({
            "ticket_id": ticket_id,
            "quality_rating": quality_rating,
            "policy_risk": policy_risk,
            "review_summary": review_summary,
            "suggested_fix": suggested_fix
        })
        
        print(f"  [Stage 3] Reviewed {ticket_id}: rating={quality_rating}, risk={policy_risk}")

    # Write output artifact safely
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "llm_review.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(llm_reviews, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: llm_review, Ticket: None, Error: Failed to write {_REVIEW_OUTPUT}: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.LLM_REVIEW_COMPLETE, llm_reviews
