from pydantic import BaseModel
from typing import Any
from pydantic import ConfigDict



class EmbeddedChunk(BaseModel):
    text: str
    embedding: list[float]
    metadata: dict[str, Any]
    model_config = ConfigDict(extra="forbid")
