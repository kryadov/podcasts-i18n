from dataclasses import dataclass
from typing import Optional


@dataclass
class Segment:
    speaker: str
    timestamp: Optional[str]
    text: str


@dataclass
class IntroInfo:
    text: str
    segment_count: int
    reason: str