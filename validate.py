import json
import os
import sys

def main():
    checks_passed = 0
    total_checks = 11

    # Define files
    required_files = [
        "outputs/normalized_tickets.json",
        "outputs/draft_replies.json",
        "outputs/policy_checks.json",
        "outputs/repaired_replies.json",
        "outputs/llm_review.json",
        "outputs/human_overrides.json",
        "outputs/final_decisions.json",
        "outputs/evaluation_report.md",
        "outputs/metrics.json",
        "logs/llm_calls.jsonl"
    ]
    
    json_files = [f for f in required_files if f.endswith(".json")]

    def pass_check(num, name):
        nonlocal checks_passed
        checks_passed += 1
        print(f"PASS: Check {num} - {name}")

    def fail_check(num, name, reason):
        print(f"FAIL: Check {num} - {name} ({reason})")

    # Check 1: Required artifacts exist
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if not missing_files:
        pass_check(1, "Required artifacts exist")
    else:
        fail_check(1, "Required artifacts exist", f"Missing files: {', '.join(missing_files)}")

    # Check 2: All JSON files parse without error
    failed_json = []
    parsed_json_data = {}
    for jf in json_files:
        if os.path.exists(jf):
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    parsed_json_data[jf] = json.load(f)
            except json.JSONDecodeError:
                failed_json.append(jf)
                
    if not failed_json and len(parsed_json_data) == len(json_files):
        pass_check(2, "All JSON files parse without error")
    else:
        fail_check(2, "All JSON files parse without error", f"Failed to parse: {', '.join(failed_json)}")

    # Check 3: tickets.json was read from disk
    try:
        with open("tickets.json", "r", encoding="utf-8") as f:
            original_tickets = json.load(f)
        original_ids = {t["ticket_id"] for t in original_tickets}
        
        normalized = parsed_json_data.get("outputs/normalized_tickets.json", [])
        norm_ids = {t["ticket_id"] for t in normalized}
        
        if original_ids and original_ids.issubset(norm_ids):
            pass_check(3, "tickets.json was read from disk")
        else:
            fail_check(3, "tickets.json was read from disk", "Normalized tickets do not contain all original ticket IDs")
    except Exception as e:
        fail_check(3, "tickets.json was read from disk", f"Error: {e}")

    # Helper for LLM calls
    llm_calls = []
    if os.path.exists("logs/llm_calls.jsonl"):
        with open("logs/llm_calls.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        llm_calls.append(json.loads(line))
                    except:
                        pass

    # Check 4: One draft_generation call per ticket
    draft_gen_count = sum(1 for c in llm_calls if c.get("stage") == "draft_generation")
    normalized_count = len(parsed_json_data.get("outputs/normalized_tickets.json", []))
    if normalized_count > 0 and draft_gen_count == normalized_count:
        pass_check(4, "One draft_generation call per ticket")
    else:
        fail_check(4, "One draft_generation call per ticket", f"Expected {normalized_count}, got {draft_gen_count}")

    # Check 5: One llm_review call per ticket
    llm_review_count = sum(1 for c in llm_calls if c.get("stage") == "llm_review")
    if normalized_count > 0 and llm_review_count == normalized_count:
        pass_check(5, "One llm_review call per ticket")
    else:
        fail_check(5, "One llm_review call per ticket", f"Expected {normalized_count}, got {llm_review_count}")

    # Check 6: Generation and review are separate stages
    allowed_stages = {"draft_generation", "repair", "llm_review"}
    stages_found = {c.get("stage") for c in llm_calls}
    invalid_stages = stages_found - allowed_stages
    
    if not invalid_stages and "draft_generation" in stages_found and "llm_review" in stages_found:
        pass_check(6, "Generation and review are separate stages")
    else:
        fail_check(6, "Generation and review are separate stages", f"Invalid stages found: {invalid_stages} or missing required stages.")

    # Check 7: reply_sections_present is present in every entry of draft_replies.json
    draft_replies = parsed_json_data.get("outputs/draft_replies.json", [])
    if draft_replies and all("reply_sections_present" in d for d in draft_replies):
        pass_check(7, "reply_sections_present is present in every draft")
    else:
        fail_check(7, "reply_sections_present is present in every draft", "Missing in one or more drafts")

    # Check 8: All policy_risk values in llm_review.json are in {"low", "medium", "high"}
    llm_reviews = parsed_json_data.get("outputs/llm_review.json", [])
    valid_risks = {"low", "medium", "high"}
    if llm_reviews and all(r.get("policy_risk") in valid_risks for r in llm_reviews):
        pass_check(8, "All policy_risk values are valid")
    else:
        fail_check(8, "All policy_risk values are valid", "Invalid risk value found")

    # Check 9: Final routing reflects deterministic rules
    final_decisions = parsed_json_data.get("outputs/final_decisions.json", [])
    policy_checks = parsed_json_data.get("outputs/policy_checks.json", [])
    human_overrides = parsed_json_data.get("outputs/human_overrides.json", {}).get("overrides", [])
    
    checks_by_id = {pc["ticket_id"]: pc["passed"] for pc in policy_checks}
    overrides_by_id = {o["ticket_id"]: o["human_override_route"] for o in human_overrides}
    normalized_by_id = {t["ticket_id"]: t for t in parsed_json_data.get("outputs/normalized_tickets.json", [])}
    
    routing_correct = True
    for fd in final_decisions:
        tid = fd["ticket_id"]
        final_route = fd["final_route"]
        
        passed_check = checks_by_id.get(tid, True)
        ticket = normalized_by_id.get(tid, {})
        tone = ticket.get("customer_tone")
        issue = ticket.get("issue_type")
        
        needs_human = (not passed_check) or (tone == "angry") or (issue == "bonus_dispute")
        
        if needs_human:
            if tid in overrides_by_id:
                # Override dictates routing
                if final_route != overrides_by_id[tid]:
                    routing_correct = False
            else:
                if final_route != "human_review":
                    routing_correct = False

    if routing_correct and final_decisions:
        pass_check(9, "Final routing reflects deterministic rules")
    else:
        fail_check(9, "Final routing reflects deterministic rules", "Routing mismatch found")

    # Check 10: evaluation_report.md contains all 5 required H2 section headers
    required_headers = [
        "## Summary",
        "## Auto-send Candidates",
        "## Human Review Required",
        "## Common Failure Patterns",
        "## Improvement Suggestions"
    ]
    report_valid = False
    if os.path.exists("outputs/evaluation_report.md"):
        with open("outputs/evaluation_report.md", "r", encoding="utf-8") as f:
            content = f.read()
            report_valid = all(h in content for h in required_headers)
            
    if report_valid:
        pass_check(10, "evaluation_report.md contains all 5 required H2 headers")
    else:
        fail_check(10, "evaluation_report.md contains all 5 required H2 headers", "Missing headers")

    # Check 11: llm_calls.jsonl contains records for both "draft_generation" and "llm_review"
    if "draft_generation" in stages_found and "llm_review" in stages_found:
        pass_check(11, "llm_calls.jsonl contains draft_generation and llm_review records")
    else:
        fail_check(11, "llm_calls.jsonl contains draft_generation and llm_review records", f"Found stages: {stages_found}")

    # Summary
    print(f"\n{checks_passed}/{total_checks} checks passed.")
    if checks_passed == total_checks:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
