from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    phone_number: str
    id: Optional[str] = None
    name: Optional[str] = None
    accessibility: bool = False


@dataclass
class Business:
    user_id: str
    id: Optional[str] = None
    brand_name: Optional[str] = None
    what_you_do: Optional[str] = None
    writing_language: Optional[str] = None
    writing_style: Optional[str] = None
    communication_preferences: Optional[str] = None
    goals: Optional[str] = None
    planning_day: Optional[int] = None
    planning_time: Optional[str] = None


@dataclass
class ConversationState:
    user_id: str
    step: int = 0
    id: Optional[str] = None
    flow: Optional[str] = None
    flow_data: Optional[dict] = None
