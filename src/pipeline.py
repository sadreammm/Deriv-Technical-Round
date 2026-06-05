import argparse
import sys
from dotenv import load_dotenv
from src.utils.state import PipelineState
from src.stages import (
    s0_load,
    s1_generate,
    s2_check,
    s2b_repair,
    s3_review,
    s4_override,
    s5_route,
    s6_report,
)

def run_pipeline(non_interactive: bool = False):
    print("Initializing Customer Support Evaluation Pipeline...")
    state = PipelineState.INIT
    print(f"Current State: {state.name}")

    try:
        # Stage 0: Load inputs
        state, tickets, policy = s0_load(state)
        print(f"Stage 0 complete. Current State: {state.name}")

        # Stage 1: Generate drafts
        state, draft_replies = s1_generate(state, tickets, policy)
        print(f"Stage 1 complete. Current State: {state.name}")

        # Stage 2: Deterministic checks
        state, policy_checks = s2_check(state, tickets, policy, draft_replies)
        print(f"Stage 2 complete. Current State: {state.name}")

        # Stage 2b: Repair (runs if deterministic checks fail)
        state, repaired_replies = s2b_repair(state, tickets, policy, draft_replies, policy_checks)
        print(f"Stage 2b complete. Current State: {state.name}")

        # Stage 3: LLM Review
        state, llm_reviews = s3_review(state, tickets, policy, draft_replies, policy_checks, repaired_replies)
        print(f"Stage 3 complete. Current State: {state.name}")

        # Stage 4: Human Override
        state = s4_override(state, non_interactive=non_interactive)
        print(f"Stage 4 complete. Current State: {state.name}")

        # Stage 5: Final Routing
        state = s5_route(state)
        print(f"Stage 5 complete. Current State: {state.name}")

        # Stage 6: Report and Metrics
        state = s6_report(state)
        print(f"Stage 6 complete. Current State: {state.name}")

        print("Pipeline execution finished successfully.")

    except NotImplementedError as e:
        print(f"\n[STUB STOP] Pipeline stopped at a stage that is not implemented yet: {e}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[PIPELINE ERROR] Pipeline execution failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    # Load environment variables from .env file
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Customer Support AI Evaluation Pipeline")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Skip human override prompt and write empty overrides"
    )
    args = parser.parse_args()

    run_pipeline(non_interactive=args.no_interactive)

if __name__ == "__main__":
    main()
