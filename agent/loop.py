from agent.state import Action, LoopState, State, Step , ToolName
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

def call_model(state:State) -> Action:
    #fake model call for now, just return a dummy action
    return Action(tool=ToolName.SUBMIT, arguments={})

def execute_action(action: Action) -> str:
    # fake: returns "ok"
    return "ok"

def run_agent_loop(state: State, settings: Settings) -> State:
    while True:
        stop_reason = check_stop_conditions(state, settings)
        if stop_reason is not None:
            state.stop_reason = stop_reason
            break
        
        action = call_model(state)
        observation = execute_action(action)
        
        step = Step(action=action, observation=observation)
        state.steps.append(step)
        
        # Update token count and spend (fake values for now)
        state.token_count += 10  # fake increment
        state.spend += 0.01  # fake increment
    
    return state