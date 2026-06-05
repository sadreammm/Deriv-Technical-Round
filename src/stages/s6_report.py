from src.utils.state import PipelineState

def run_stage(state: PipelineState) -> PipelineState:
    if state != PipelineState.FINAL_ROUTING_DECIDED:
        raise ValueError(f"Invalid predecessor state: {state}")
    raise NotImplementedError("s6_report stage not implemented")
