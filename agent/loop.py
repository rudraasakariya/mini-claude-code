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
    
    if len(state.steps) >= settings.last_action_repeat_limit:
        last_actions = [step.action for step in state.steps[-settings.last_action_repeat_limit:]]
        if all(action == last_actions[0] for action in last_actions):
            return LoopState.REPEATED_ACTION
    
    return None