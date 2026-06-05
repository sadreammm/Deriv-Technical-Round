import json
import os
import sys
from collections import Counter

from src.utils.state import PipelineState, OUTPUTS_DIR


def run_stage(
    state: PipelineState,
    tickets: list,
    final_decisions: list,
    llm_reviews: list,
    repaired_replies: list,
    policy_checks: list
) -> PipelineState:
    """
    Stage 6: Reporting.
    Aggregates metrics and generates the final markdown report.
    """
    if state != PipelineState.FINAL_ROUTING_DECIDED:
        print(
            f"[PIPELINE ERROR] Stage: report, Ticket: None, "
            f"Error: Expected FINAL_ROUTING_DECIDED, got {state.name}",
            file=sys.stderr
        )
        sys.exit(1)

    # Fast Lookups
    decisions_by_id = {d["ticket_id"]: d for d in final_decisions}
    reviews_by_id = {lr["ticket_id"]: lr for lr in llm_reviews}
    checks_by_id = {pc["ticket_id"]: pc for pc in policy_checks}
    tickets_by_id = {t["ticket_id"]: t for t in tickets}

    # Metric Aggregations
    total_tickets = len(tickets)
    
    auto_send_count = sum(1 for d in final_decisions if d["final_route"] == "auto_send")
    human_review_count = sum(1 for d in final_decisions if d["final_route"] == "human_review")
    
    pass_count = sum(1 for pc in policy_checks if pc["passed"])
    deterministic_pass_rate = pass_count / total_tickets if total_tickets > 0 else 0.0
    
    ratings = [lr["quality_rating"] for lr in llm_reviews if isinstance(lr.get("quality_rating"), int)]
    average_quality_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    
    repair_attempted_count = len(repaired_replies)
    repair_success_count = sum(1 for r in repaired_replies if not r.get("still_failed_checks"))

    # Write metrics.json
    metrics_data = {
        "total_tickets": total_tickets,
        "auto_send_count": auto_send_count,
        "human_review_count": human_review_count,
        "deterministic_pass_rate": deterministic_pass_rate,
        "average_quality_rating": average_quality_rating,
        "repair_attempted_count": repair_attempted_count,
        "repair_success_count": repair_success_count
    }
    
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    metrics_path = os.path.join(OUTPUTS_DIR, "metrics.json")
    try:
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: report, Ticket: None, Error: Failed to write metrics.json: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate Markdown Report
    report_lines = []
    
    # 1. Summary
    report_lines.append("## Summary\n")
    report_lines.append(f"- **Total Tickets**: {total_tickets}")
    report_lines.append(f"- **Auto-send Count**: {auto_send_count}")
    report_lines.append(f"- **Human Review Count**: {human_review_count}")
    report_lines.append(f"- **Deterministic Pass Rate**: {deterministic_pass_rate:.2%}")
    report_lines.append(f"- **Average Quality Rating**: {average_quality_rating}\n")
    
    # 2. Auto-send Candidates
    report_lines.append("## Auto-send Candidates\n")
    auto_sends = [d for d in final_decisions if d["final_route"] == "auto_send"]
    if auto_sends:
        for d in auto_sends:
            tid = d["ticket_id"]
            issue_type = tickets_by_id[tid]["issue_type"]
            q_rating = reviews_by_id.get(tid, {}).get("quality_rating", "N/A")
            report_lines.append(f"- **{tid}** ({issue_type}) - Quality Rating: {q_rating}")
            report_lines.append(f"  - *Reasoning*: {d['decision_reason']}")
    else:
        report_lines.append("- No tickets were routed for auto-send.\n")
    report_lines.append("\n")

    # 3. Human Review Required
    report_lines.append("## Human Review Required\n")
    human_reviews = [d for d in final_decisions if d["final_route"] == "human_review"]
    if human_reviews:
        for d in human_reviews:
            tid = d["ticket_id"]
            issue_type = tickets_by_id[tid]["issue_type"]
            failed_checks = checks_by_id[tid]["failed_checks"]
            failed_str = ", ".join(failed_checks) if failed_checks else "None"
            
            report_lines.append(f"- **{tid}** ({issue_type})")
            report_lines.append(f"  - *Failed Checks*: {failed_str}")
            report_lines.append(f"  - *Reasoning*: {d['decision_reason']}")
    else:
        report_lines.append("- No tickets require human review.\n")
    report_lines.append("\n")

    # 4. Common Failure Patterns
    report_lines.append("## Common Failure Patterns\n")
    all_failed_checks = []
    for pc in policy_checks:
        all_failed_checks.extend(pc["failed_checks"])
        
    medium_high_risks = [lr["policy_risk"] for lr in llm_reviews if lr["policy_risk"] in ["medium", "high"]]
    
    if all_failed_checks:
        counts = Counter(all_failed_checks)
        report_lines.append("The deterministic evaluation engine flagged the following rule violations across the batch:")
        for check, count in counts.most_common():
            report_lines.append(f"- **{check}**: {count} occurrences")
    else:
        report_lines.append("- No deterministic checks failed across this batch. Generation compliance is high.")
        
    report_lines.append("")
    if medium_high_risks:
        risk_counts = Counter(medium_high_risks)
        report_lines.append("The LLM Reviewer flagged the following subjective policy risks:")
        for risk, count in risk_counts.most_common():
            report_lines.append(f"- **{risk.capitalize()} Risk**: {count} occurrences")
    else:
        report_lines.append("- The LLM Reviewer did not flag any Medium or High policy risks.")
    report_lines.append("\n")

    # 5. Improvement Suggestions
    report_lines.append("## Improvement Suggestions\n")
    if all_failed_checks or medium_high_risks:
        report_lines.append("1. **Enhance Generation Prompts**: Consider modifying the system prompt in Stage 1 to explicitly emphasize the rules that failed most frequently, particularly focusing on tone adjustments or hardcoded timeline bans.")
        report_lines.append("2. **Iterative Repair Tuning**: Review the failed outputs against the `policy.json` requirements. If valid standard operating procedures are being incorrectly flagged, consider refining the regex boundaries in the deterministic engine to reduce false positives.")
    else:
        report_lines.append("1. **Expand Test Coverage**: Since all tickets passed compliance checks effortlessly, consider injecting edge-cases and adversarial tone tickets into `tickets.json` to truly stress test the pipeline's deterministic regex guardrails.")
        report_lines.append("2. **Tighten Rubric Requirements**: If generation quality is plateauing, consider updating the `quality_rubric` inside `policy.json` to demand higher empathy or cross-selling initiatives to push the LLM reviewer into evaluating more strictly.")

    report_path = os.path.join(OUTPUTS_DIR, "evaluation_report.md")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
    except Exception as e:
        print(f"[PIPELINE ERROR] Stage: report, Ticket: None, Error: Failed to write evaluation_report.md: {e}", file=sys.stderr)
        sys.exit(1)

    print("  [Stage 6] Wrote metrics.json and evaluation_report.md successfully.")
    
    return PipelineState.REPORT_GENERATED
