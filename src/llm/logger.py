import hashlib
import json
import os
from datetime import datetime, timezone
from src.utils.state import LLM_LOG_PATH

def log_llm_call(
    stage: str,
    ticket_id: str,
    model: str,
    prompt: str,
    response_text: str,
    input_artifacts: list = None,
    output_artifact: str = None
) -> None:
    """
    Log an LLM call to logs/llm_calls.jsonl in append-only JSON Lines format.
    """
    prompt_hash_val = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    prompt_hash = f"sha256:{prompt_hash_val}"
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    if input_artifacts is None:
        input_artifacts = ["tickets.json", "policy.json"]
        
    if output_artifact is None:
        if stage == "draft_generation":
            output_artifact = "outputs/draft_replies.json"
        elif stage == "repair":
            output_artifact = "outputs/repaired_replies.json"
        elif stage == "llm_review":
            output_artifact = "outputs/llm_review.json"
        else:
            output_artifact = ""

    log_entry = {
        "stage": stage,
        "ticket_id": ticket_id,
        "timestamp": timestamp,
        "provider": "anthropic",
        "model": model,
        "prompt_hash": prompt_hash,
        "input_artifacts": input_artifacts,
        "output_artifact": output_artifact
    }
    
    log_dir = os.path.dirname(LLM_LOG_PATH)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        
    with open(LLM_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
