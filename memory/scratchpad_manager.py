from short_term_memory import ShortTermMemory
from schemas import AgentStep


def agent_step(memory: ShortTermMemory, response: AgentStep):
    
    print(">>> agent_step() called")

    if response.plan_updated:
        memory.update_plan(
            response.new_plan,
            response.next_subgoal
        )

    memory.update_reasoning(response.thought)

    if response.action == "respond":
        memory.add(
            "assistant",
            response.final_answer
        )

    return response