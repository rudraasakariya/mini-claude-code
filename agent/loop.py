from agent.state import LoopState, State , ToolName
from config.settings import Settings


def check_stop_conditions(state: State , settings: Settings) -> LoopState | None:
    if state.steps and state.steps[-1].action.tool == ToolName.SUBMIT:
        return LoopState.SUBMIT_CALLED
    
    if len(state.steps) >= settings.max_steps:
        return LoopState.STEP_LIMIT_HIT
    
    if state.token_count >= settings.max_tokens:
        return LoopState.TOKEN_BUDGET_HIT
    
    if state.spend >= settings.max_spend:
        return LoopState.COST_CEILING_HIT
    
    return None