from src.utils.state import PipelineState

def run_stage(state: PipelineState) -> PipelineState:
    if state != PipelineState.HUMAN_OVERRIDE_COMPLETE:
        raise ValueError(f"Invalid predecessor state: {state}")
    raise NotImplementedError("s5_route stage not implemented")
