import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "poolside/laguna-s-2.1:free"


def summarize(prompt, turns):

    conversation = "\n".join(
        f"{t['role']}: {t['content']}"
        for t in turns
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": conversation,
            },
        ],
    )

    return response.choices[0].message.content