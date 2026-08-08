import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "poolside/laguna-s-2.1:free",
)


client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


SUMMARY_PROMPT = """
You are a conversation memory compressor for Copper Leaf Kitchen.

Summarize the conversation while preserving:

- customer allergies
- dietary restrictions
- important customer requests
- decisions already made
- unresolved issues
- important constraints
- order-related facts
- safety-critical information

Never remove or generalize an allergy or food-safety fact.

Discard:

- repetitive tool output
- irrelevant inventory data
- redundant JSON
- repeated status information

Return a concise factual summary.
"""


def summarize(turns: list[dict]) -> tuple[str, dict]:

    conversation = "\n".join(
        f"{turn.get('role', '')}: {turn.get('content', '')}"
        for turn in turns
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": SUMMARY_PROMPT,
            },
            {
                "role": "user",
                "content": conversation,
            },
        ],
    )

    usage = response.usage

    usage_data = {
        "input_tokens": getattr(
            usage,
            "prompt_tokens",
            0,
        ),
        "output_tokens": getattr(
            usage,
            "completion_tokens",
            0,
        ),
    }

    return response.choices[0].message.content, usage_data