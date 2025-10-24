from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Note:
    id: str
    text: str
    meeting_date: str
    created_at: str
    is_addendum: bool = False

@dataclass
class Item:
    id: str
    description: str
    status: str  # OPEN, INFO, CLOSED
    assignee_id: Optional[str]
    priority: str  # Low, Normal, High
    due_date: Optional[str]
    tags: List[str]
    order: int
    section_name: str
    notes: List[Note] = field(default_factory=list)

@dataclass
class Section:
    id: str
    name: str
    order: int

@dataclass
class MeetingHeader:
    topic: str
    date: str
    start: str
    end: str
    location: str
    teams_link: str

@dataclass
class Meeting:
    id: str
    number: str
    header: MeetingHeader
    sections: List[Section] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)
    finalized_at: str | None = None

@dataclass
class Track:
    id: str
    name: str
    slug: str
    defaults_location: str = ""
    defaults_teams_link: str = ""
    roster: List[str] = field(default_factory=list)
    section_templates: List[str] = field(default_factory=list)
    recurrence_mode: str = "weekly"   # weekly, biweekly, monthly
    recurrence_interval: int = 1

@dataclass
class Project:
    id: str
    name: str
    slug: str
    tracks: List[Track] = field(default_factory=list)
