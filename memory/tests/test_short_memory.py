from short_term_memory import ShortTermMemory
from scratchpad_manager import agent_step
from schemas import AgentStep

from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

memory = ShortTermMemory(max_turns=4)

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

SYSTEM_PROMPT = """
You are an AI agent.

Always respond with ONLY valid JSON.

The JSON MUST exactly follow this schema:

{
    "thought": "Brief reasoning about the user's request.",
    "action": "respond",
    "action_input": null,
    "final_answer": "Your response to the user.",
    "plan_updated": false,
    "new_plan": null,
    "next_subgoal": null
}

Rules:
- Return JSON only.
- Do NOT use markdown.
- Do NOT add explanations.
- Do NOT wrap the JSON in ``` blocks.

- "action" must be one of:
    - "respond"
    - "call_tool"
    - "replan"

- If answering the user directly:
    action = "respond"

- If answering requires an external tool:
    action = "call_tool"
    Fill action_input with the required tool information.

- If the user starts or changes a multi-step task:
    set plan_updated = true
    provide new_plan
    provide next_subgoal

- Otherwise:
    plan_updated = false
"""

print("Write your request (type 'exit' to quit)\n")

while True:

    user_input = input("User: ").strip()

    if user_input.lower() == "exit":
        break

    # Store the user's message
    memory.add("user", user_input)

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    messages.extend(memory.get_context())

    response = client.responses.create(
        model="poolside/laguna-s-2.1:free",
        input=messages
    )

    # Optional while debugging
    print("\nRaw LLM Output:")
    print(response.output_text)

    # Convert JSON -> AgentStep
    try:
        agent_response = AgentStep.model_validate_json(
            response.output_text
        )

    except Exception:
        print("Model returned invalid JSON:")
        print(response.output_text)
        continue

    # Update scratchpad + assistant memory
    agent_step(memory, agent_response)

    # Show only the assistant's final answer
    print(f"\nAssistant: {agent_response.final_answer}\n")