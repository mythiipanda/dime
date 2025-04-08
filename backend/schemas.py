from pydantic import BaseModel
from typing import Dict, Any

class AnalyzeRequest(BaseModel):
    query: str = "Provide a general analysis of the data."
    data: Dict[str, Any]

class FetchRequest(BaseModel):
    target: str
    params: Dict[str, Any] = {}
    prompt: str | None = None

class NormalizeRequest(BaseModel):
    raw_data: Dict[str, Any]