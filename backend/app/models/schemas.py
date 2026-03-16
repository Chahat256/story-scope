from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class UploadResponse(BaseModel):
    job_id: str
    filename: str
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int  # 0-100
    message: str
    filename: str
    created_at: datetime
    updated_at: datetime


# === Analysis Schemas ===

class SupportingPassage(BaseModel):
    text: str
    page_reference: Optional[str] = None
    relevance: str


class CharacterAnalysis(BaseModel):
    name: str
    aliases: List[str] = []
    role: str  # protagonist, antagonist, supporting, etc.
    defining_traits: List[str]
    goals: List[str]
    conflicts: List[str]
    important_relationships: List[str]
    supporting_passages: List[SupportingPassage]
    confidence: str = "moderate"  # high, moderate, low


class RelationshipType(str, Enum):
    FRIENDSHIP = "friendship"
    RIVALRY = "rivalry"
    ROMANCE = "romance"
    FAMILY = "family"
    MENTORSHIP = "mentorship"
    ALLIANCE = "alliance"
    CONFLICT = "conflict"
    COMPLEX = "complex"


class RelationshipAnalysis(BaseModel):
    character_a: str
    character_b: str
    relationship_type: RelationshipType
    description: str
    dynamics: str
    supporting_passages: List[SupportingPassage]
    confidence: str = "moderate"


class ThemeAnalysis(BaseModel):
    theme: str
    description: str
    motifs: List[str]
    supporting_passages: List[SupportingPassage]
    prevalence: str  # central, significant, minor


class TropeAnalysis(BaseModel):
    trope_name: str
    trope_id: str
    confidence: str  # strongly supported, moderately supported, weakly supported
    explanation: str
    supporting_passages: List[SupportingPassage]
    related_characters: List[str]


class NovelOverview(BaseModel):
    title_guess: str
    author_guess: Optional[str] = None
    genre_guess: str
    setting_description: str
    narrative_summary: str
    estimated_time_period: Optional[str] = None
    point_of_view: str
    tone: str


class AnalysisReport(BaseModel):
    job_id: str
    overview: NovelOverview
    characters: List[CharacterAnalysis]
    relationships: List[RelationshipAnalysis]
    themes: List[ThemeAnalysis]
    tropes: List[TropeAnalysis]
    created_at: datetime


class ChatMessage(BaseModel):
    role: str  # user, assistant
    content: str


class ChatRequest(BaseModel):
    job_id: str
    message: str
    history: List[ChatMessage] = []


class ChatResponse(BaseModel):
    response: str
    sources: List[SupportingPassage] = []
    confidence: str = "moderate"
