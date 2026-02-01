from pydantic import BaseModel
from typing import Optional, Any, Dict

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None