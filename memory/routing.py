import json
import os
from pathlib import Path
from episodic_memory import EpisodicMemory

from openai import OpenAI

from schemas import (
    MemoryItem,
    MemoryRoutingDecision,
)
from dotenv import load_dotenv

load_dotenv()

LOG_FILE = Path("logs/routing_log.json")

PROMPT_FILE = Path("prompts/prompt.txt")
if not PROMPT_FILE.exists():
    raise FileNotFoundError("prompts/prompt.txt not found")

PROMPT = PROMPT_FILE.read_text(encoding="utf-8")


class PromoteOrDropRouter:

    def __init__(self):

        self.client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )
        self.episodic_memory = EpisodicMemory()


        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not LOG_FILE.exists():
            LOG_FILE.write_text("[]")

    def route(
        self,
        item: MemoryItem,
        user_id: str

    ) -> MemoryRoutingDecision:

        try:
            decision = self._llm_decision(item)
            if decision.destination == "episodic":

                self.episodic_memory.add_episode(

                    user_id=user_id,

                    event=decision.event_summary or item.content,

                    metadata={

                        "category": decision.category,

                        "importance": decision.importance_score,

                        "reasoning": decision.reasoning,

                        "context": decision.context,

                        "outcome": decision.outcome

                    }

        )


        except Exception as e:

            print(f"LLM failed: {e}")

            decision = MemoryRoutingDecision(
                destination="forget",
                reasoning="LLM unavailable.",
                importance_score=0.0,
                category="other"
            )

        self._log(item, decision)
        
        return decision
    


    def _llm_decision(
        self,
        item: MemoryItem
    ) -> MemoryRoutingDecision:

        prompt = PROMPT.format(
            role=item.role,
            message=item.content
        )

        response = self.client.responses.create(
            model="poolside/laguna-s-2.1:free",
            input=prompt,
        )

        text = response.output_text.strip()

        return MemoryRoutingDecision.model_validate_json(text)

    def _log(
        self,
        item: MemoryItem,
        decision: MemoryRoutingDecision
    ):

        with open(LOG_FILE, "r") as f:
            logs = json.load(f)

        logs.append({

            "message": item.content,

            "role": item.role,

            "timestamp": item.timestamp.isoformat(),

            "decision": decision.destination,

            "reasoning": decision.reasoning,

            "importance_score": decision.importance_score,

            "category": decision.category,

            "event_summary":decision.event_summary
        })

        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=4)