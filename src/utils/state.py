"""
Pipeline state enum and global configuration constants.

All stage functions must validate the incoming state against the expected
predecessor state before doing any work.
"""

from enum import Enum, auto


class PipelineState(Enum):
    """Ordered states that the pipeline progresses through, one per stage."""

    INIT = auto()
    INPUTS_LOADED = auto()
    DRAFT_REPLIES_GENERATED = auto()
    DETERMINISTIC_CHECKS_COMPLETE = auto()
    LLM_REVIEW_COMPLETE = auto()
    HUMAN_OVERRIDE_COMPLETE = auto()
    FINAL_ROUTING_DECIDED = auto()
    REPORT_GENERATED = auto()
    VALIDATION_COMPLETE = auto()
    RESULTS_FINALISED = auto()


# ---------------------------------------------------------------------------
# LLM model identifiers
# ---------------------------------------------------------------------------
GENERATION_MODEL: str = "claude-haiku-4-5"
REVIEW_MODEL: str = "claude-haiku-4-5"
MAX_TOKENS: int = 1024

# ---------------------------------------------------------------------------
# File-system paths
# ---------------------------------------------------------------------------
TICKETS_PATH: str = "tickets.json"
POLICY_PATH: str = "policy.json"
OUTPUTS_DIR: str = "outputs/"
LOGS_DIR: str = "logs/"
LLM_LOG_PATH: str = "logs/llm_calls.jsonl"
