import os
import sys
from anthropic import Anthropic

def get_client() -> Anthropic:
    """
    Initialize and return the Anthropic API client.
    Fails fast if the ANTHROPIC_API_KEY is not set or placeholder.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_key_here":
        print("[PIPELINE ERROR] Stage: INIT, Ticket: None, Error: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return Anthropic(api_key=api_key)

def call_model(
    client: Anthropic,
    model: str,
    prompt: str,
    system_prompt: str = None,
    max_tokens: int = 1024,
    stage: str = None,
    ticket_id: str = None,
    input_artifacts: list = None,
    output_artifact: str = None
) -> str:
    """
    Call the Anthropic API with the specified parameters.
    Fails fast (exits with code 1) on any API or parsing error.
    Logs the call via log_llm_call.
    """
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}]
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    try:
        response = client.messages.create(**kwargs)
        if not response.content or len(response.content) == 0:
            raise ValueError("Empty response received from LLM")
        
        response_text = response.content[0].text
        
        # Log the call using the internal logger
        from .logger import log_llm_call
        log_llm_call(
            stage=stage,
            ticket_id=ticket_id,
            model=model,
            prompt=prompt,
            response_text=response_text,
            input_artifacts=input_artifacts,
            output_artifact=output_artifact
        )
        
        return response_text
    except Exception as e:
        error_msg = str(e)
        print(f"[PIPELINE ERROR] Stage: {stage}, Ticket: {ticket_id}, Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
