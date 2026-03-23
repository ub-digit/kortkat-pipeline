from typing import List, Union, Literal, Dict, Any
from pydantic import BaseModel

class TextPart(BaseModel):
    type: Literal["text"]
    data: str

class InlineDataPart(BaseModel):
    type: Literal["inlineData"]
    mimeType: str
    data: str

Part = Union[TextPart, InlineDataPart]

class Content(BaseModel):
    role: str
    parts: List[Part]

class PromptData(BaseModel):
    key: str
    prompt: List[Content]
    system_instruction: str
    json_schema: Union[str, Dict[str, Any]]