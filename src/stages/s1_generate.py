"""
Stage 1: Draft Reply Generation
"""
import json
import os
import sys

from src.utils.state import (
    PipelineState,
    GENERATION_MODEL,
    MAX_TOKENS,
    OUTPUTS_DIR,
)
from src.llm.client import get_client, call_model

_SYSTEM_PROMPT = (
    "You are a professional customer support agent. "
    "You must follow the policy constraints provided. "
    "Never make forbidden claims. "
    "Always include all required reply sections."
)

_DRAFT_GENERATION_OUTPUT = "outputs/draft_replies.json"
_INPUT_ARTIFACTS = ["tickets.json", "policy.json"]


def _build_prompt(ticket: dict, policy: dict) -> str:
    """
    Construct the user-turn prompt from the ticket and policy data.
    """
    required_sections = ", ".join(policy["required_reply_sections"])
    forbidden_claims = ", ".join(policy["forbidden_claims"])

    # Interpolate all required fields from the ticket and policy
    prompt = (
        f"Ticket: {json.dumps(ticket)}\n"
        f"Account Context: {json.dumps(ticket['account_context'])}\n"
        f"Policy - Required sections: {required_sections}\n"
        f"Policy - Forbidden claims: {forbidden_claims}\n\n"
        f"Write a support reply that includes: {required_sections}.\n"
        f"Do not: {forbidden_claims}.\n"
        f"Do not ask for the customer's password.\n"
        f"Do not make promises about timelines or account approvals you cannot guarantee."
    )
    return prompt


def _compute_sections_present(reply_text: str, required_sections: list[str]) -> list[str]:
    """
    Check (case-insensitively) which required section keywords appear in reply_text.
    """
    reply_lower = reply_text.lower()
    return [
        section for section in required_sections
        if section.lower().replace("_", " ") in reply_lower or section.lower() in reply_lower
    ]


def run_stage(
    state: PipelineState,
    tickets: list,
    policy: dict,
) -> tuple[PipelineState, list]:
    """
    Stage 1: Generate one draft reply per ticket.
    """
    # 1. Assert correct predecessor state
    if state != PipelineState.INPUTS_LOADED:
        print(
            f"[PIPELINE ERROR] Stage: draft_generation, Ticket: None, "
            f"Error: Expected state {PipelineState.INPUTS_LOADED.name}, got {state.name}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Get Anthropic client
    client = get_client()
    draft_replies = []

    # 3. Iterate over tickets one by one
    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        prompt = _build_prompt(ticket, policy)

        # 4. Call LLM (call_model handles the fail-fast error and logging)
        reply_text = call_model(
            client=client,
            model=GENERATION_MODEL,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            max_tokens=MAX_TOKENS,
            stage="draft_generation",
            ticket_id=ticket_id,
            input_artifacts=_INPUT_ARTIFACTS,
            output_artifact=_DRAFT_GENERATION_OUTPUT,
        )

        # 5. Compute sections present in Python
        sections_present = _compute_sections_present(
            reply_text, policy["required_reply_sections"]
        )

        draft_replies.append({
            "ticket_id": ticket_id,
            "reply_text": reply_text,
            "reply_sections_present": sections_present,
        })
        print(f"  [Stage 1] Generated draft for {ticket_id}")

    # 6. Accumulate and write outputs
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "draft_replies.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(draft_replies, f, indent=2)
    except OSError as e:
        print(
            f"[PIPELINE ERROR] Stage: draft_generation, Ticket: None, "
            f"Error: Failed to write {_DRAFT_GENERATION_OUTPUT}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 7. Return state and draft replies
    return PipelineState.DRAFT_REPLIES_GENERATED, draft_replies
