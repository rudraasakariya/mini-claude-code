from agent.state import LoopState, State , ToolName
from enum import Enum

def check_stop_conditions(state: State) -> LoopState | None:
    if state.steps and state.steps[-1].action.tool == ToolName.SUBMIT:
        return LoopState.SUBMIT_CALLED
    
    return None