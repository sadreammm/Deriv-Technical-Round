import json
import os
import sys

from src.utils.state import PipelineState, OUTPUTS_DIR


def run_stage(
    state: PipelineState,
    tickets: list,
    policy_checks: list,
    llm_reviews: list,
    non_interactive: bool = False
) -> tuple[PipelineState, list]:
    """
    Stage 4: Human Override.
    Calculates preliminary routing and allows the operator to intervene interactively via stdin.
    """
    if state != PipelineState.LLM_REVIEW_COMPLETE:
        print(
            f"[PIPELINE ERROR] Stage: human_override, Ticket: None, "
            f"Error: Expected state LLM_REVIEW_COMPLETE, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)

    checks_by_id = {pc["ticket_id"]: pc for pc in policy_checks}
    reviews_by_id = {lr["ticket_id"]: lr for lr in llm_reviews}
    
    # Print formatted summary table
    print("\n" + "=" * 70)
    print(f"{'Ticket':<10} | {'Det. Check':<12} | {'Quality':<7} | {'Policy Risk':<12} | {'Initial Route':<15}")
    print("-" * 70)
    
    ticket_ids = []
    
    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        ticket_ids.append(ticket_id)
        
        pc = checks_by_id[ticket_id]
        lr = reviews_by_id.get(ticket_id, {})
        
        # Compute preliminary initial_route
        if not pc["passed"]:
            initial_route = "human_review"
        elif ticket.get("customer_tone") == "angry":
            initial_route = "human_review"
        elif ticket.get("issue_type") == "bonus_dispute":
            initial_route = "human_review"
        else:
            initial_route = "auto_send"
            
        det_check_str = "PASS" if pc["passed"] else "FAIL"
        quality = lr.get("quality_rating", "N/A")
        risk = lr.get("policy_risk", "N/A")
        
        print(f"{ticket_id:<10} | {det_check_str:<12} | {quality:<7} | {risk:<12} | {initial_route:<15}")
        
    print("=" * 70 + "\n")
    
    overrides = []
    
    # Process interactions
    if non_interactive:
        print("  [Stage 4] Running in --no-interactive mode. No overrides accepted.")
    else:
        print("Enter any ticket overrides as: <ticket_id> <auto_send|human_review>")
        print("Press Enter on an empty line to continue.")
        
        while True:
            try:
                line = input().strip()
            except EOFError:
                break
                
            if not line:
                break
                
            parts = line.split()
            if len(parts) != 2:
                print(f"Warning: Invalid format for '{line}'. Please use: <ticket_id> <route>")
                continue
                
            ticket_id, route = parts[0], parts[1]
            if ticket_id not in ticket_ids:
                print(f"Warning: Unrecognized ticket_id '{ticket_id}'. Skipping.")
                continue
                
            if route not in ["auto_send", "human_review"]:
                print(f"Warning: Invalid route '{route}'. Must be 'auto_send' or 'human_review'.")
                continue
                
            overrides.append({
                "ticket_id": ticket_id,
                "human_override_route": route
            })
            print(f"  Override recorded: {ticket_id} -> {route}")

    # Write output
    output_data = {
        "overrides": overrides,
        "non_interactive_mode": non_interactive
    }
    
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUTS_DIR, "human_overrides.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: human_override, Ticket: None, Error: Failed to write human_overrides.json: {e}", file=sys.stderr)
        sys.exit(1)
        
    return PipelineState.HUMAN_OVERRIDE_COMPLETE, overrides
