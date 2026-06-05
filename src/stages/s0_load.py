import json
import os
import sys
from pathlib import Path
from src.utils.state import PipelineState, TICKETS_PATH, POLICY_PATH, OUTPUTS_DIR

def run_stage(state: PipelineState) -> tuple[PipelineState, list, dict]:
    """
    Stage 0: Load and validate inputs from disk.
    Reads tickets.json and policy.json, runs validation, normalizes tickets,
    writes normalized_tickets.json, and transitions the pipeline state.
    """
    # 1. Assert state is PipelineState.INIT
    if state != PipelineState.INIT:
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Expected predecessor state {PipelineState.INIT}, got {state}", file=sys.stderr)
        sys.exit(1)
        
    tickets_file = Path(TICKETS_PATH)
    policy_file = Path(POLICY_PATH)
    
    # 2. Read tickets.json and policy.json from disk
    if not tickets_file.exists():
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: File '{TICKETS_PATH}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not policy_file.exists():
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: File '{POLICY_PATH}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    try:
        tickets_raw = tickets_file.read_text(encoding="utf-8")
        tickets = json.loads(tickets_raw)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Failed to parse '{TICKETS_PATH}': {e}", file=sys.stderr)
        sys.exit(1)
        
    try:
        policy_raw = policy_file.read_text(encoding="utf-8")
        policy = json.loads(policy_raw)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Failed to parse '{POLICY_PATH}': {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Validate policy structure
    required_policy_keys = [
        "allowed_issue_types",
        "required_reply_sections",
        "forbidden_claims",
        "routing_rules",
        "quality_rubric"
    ]
    if not isinstance(policy, dict):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: policy.json must be a JSON object", file=sys.stderr)
        sys.exit(1)
        
    for key in required_policy_keys:
        if key not in policy:
            print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy is missing required key '{key}'", file=sys.stderr)
            sys.exit(1)
            
    # Check types for policy keys
    if not isinstance(policy["allowed_issue_types"], list):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy key 'allowed_issue_types' must be a list of strings", file=sys.stderr)
        sys.exit(1)
    if not isinstance(policy["required_reply_sections"], list):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy key 'required_reply_sections' must be a list of strings", file=sys.stderr)
        sys.exit(1)
    if not isinstance(policy["forbidden_claims"], list):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy key 'forbidden_claims' must be a list of strings", file=sys.stderr)
        sys.exit(1)
    if not isinstance(policy["routing_rules"], dict):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy key 'routing_rules' must be an object", file=sys.stderr)
        sys.exit(1)
    if not isinstance(policy["quality_rubric"], dict):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Policy key 'quality_rubric' must be an object", file=sys.stderr)
        sys.exit(1)

    # 4. Validate tickets structure
    if not isinstance(tickets, list):
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: tickets.json must be a JSON array", file=sys.stderr)
        sys.exit(1)
        
    required_ticket_keys = {
        "ticket_id": str,
        "customer_tone": str,
        "issue_type": str,
        "customer_message": str,
        "account_context": dict
    }
    
    for idx, ticket in enumerate(tickets):
        if not isinstance(ticket, dict):
            print(f"[PIPELINE ERROR] Stage: INIT, Ticket: Index {idx}, Error: Ticket must be a JSON object", file=sys.stderr)
            sys.exit(1)
            
        ticket_id = ticket.get("ticket_id", f"Index {idx}")
        
        # Verify required keys & types
        for key, expected_type in required_ticket_keys.items():
            if key not in ticket:
                print(f"[PIPELINE ERROR] Stage: INIT, Ticket: {ticket_id}, Error: Ticket is missing required key '{key}'", file=sys.stderr)
                sys.exit(1)
            if not isinstance(ticket[key], expected_type):
                print(f"[PIPELINE ERROR] Stage: INIT, Ticket: {ticket_id}, Error: Ticket key '{key}' must be of type {expected_type.__name__}", file=sys.stderr)
                sys.exit(1)
                
        # Validate issue_type is in allowed_issue_types
        if ticket["issue_type"] not in policy["allowed_issue_types"]:
            print(f"[PIPELINE ERROR] Stage: INIT, Ticket: {ticket_id}, Error: Ticket issue_type '{ticket['issue_type']}' is not in policy allowed list: {policy['allowed_issue_types']}", file=sys.stderr)
            sys.exit(1)

    # 5. Write normalized tickets to outputs/normalized_tickets.json
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    normalized_path = os.path.join(OUTPUTS_DIR, "normalized_tickets.json")
    try:
        with open(normalized_path, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: Failed to write to {normalized_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.INPUTS_LOADED, tickets, policy
