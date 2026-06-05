from src.utils.state import PipelineState

def run_stage(state: PipelineState, non_interactive: bool = False) -> PipelineState:
    if state != PipelineState.LLM_REVIEW_COMPLETE:
        raise ValueError(f"Invalid predecessor state: {state}")
    raise NotImplementedError("s4_override stage not implemented")
