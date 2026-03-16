from groq import Groq
import json
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.core.config import settings
from app.models.schemas import (
    AnalysisReport, NovelOverview, CharacterAnalysis, RelationshipAnalysis,
    ThemeAnalysis, TropeAnalysis, SupportingPassage, RelationshipType
)
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)

# Predefined trope library for MVP
TROPE_LIBRARY = [
    {"id": "chosen_one", "name": "The Chosen One", "description": "A character destined or selected to fulfill a special purpose"},
    {"id": "redemption_arc", "name": "Redemption Arc", "description": "A character moving from wrongdoing or failure toward moral recovery"},
    {"id": "reluctant_hero", "name": "Reluctant Hero", "description": "A protagonist who doesn't want the heroic role thrust upon them"},
    {"id": "coming_of_age", "name": "Coming of Age", "description": "A protagonist's journey from youth to maturity, often through trials"},
    {"id": "forbidden_love", "name": "Forbidden Love", "description": "A romantic relationship opposed by society, family, or circumstance"},
    {"id": "mentor_student", "name": "Mentor and Student", "description": "A wise guide shapes a younger, less experienced protagonist"},
    {"id": "fish_out_of_water", "name": "Fish Out of Water", "description": "A character placed in an environment completely foreign to them"},
    {"id": "dark_secret", "name": "Dark Secret", "description": "A hidden truth that, if revealed, would change everything"},
    {"id": "found_family", "name": "Found Family", "description": "Characters forming deep familial bonds outside biological family"},
    {"id": "rival_turned_ally", "name": "Rival Turned Ally", "description": "An adversary who becomes a companion through shared experience"},
    {"id": "tragic_villain", "name": "Tragic Villain", "description": "An antagonist whose evil is rooted in understandable pain or loss"},
    {"id": "love_triangle", "name": "Love Triangle", "description": "A protagonist torn between two romantic interests"},
    {"id": "power_corrupts", "name": "Power Corrupts", "description": "A character's acquisition of power leads to their moral downfall"},
    {"id": "quest_narrative", "name": "Quest Narrative", "description": "Characters pursuing a specific goal through a series of trials"},
    {"id": "dystopia", "name": "Dystopian Society", "description": "A story set in an oppressive, controlled, or degraded society"},
    {"id": "revenge_plot", "name": "Revenge Plot", "description": "A protagonist driven by desire for vengeance"},
    {"id": "identity_discovery", "name": "Identity Discovery", "description": "A character uncovering the truth about who they really are"},
    {"id": "sacrifice", "name": "Heroic Sacrifice", "description": "A character gives up something precious (including their life) for others"},
    {"id": "unreliable_narrator", "name": "Unreliable Narrator", "description": "The story's narrator whose credibility is compromised"},
    {"id": "social_class_conflict", "name": "Class Conflict", "description": "Tension between characters of different social or economic strata"},
    {"id": "man_vs_nature", "name": "Man vs. Nature", "description": "Characters in conflict with the natural world"},
    {"id": "prophecy", "name": "Prophecy", "description": "A foretold future event that drives character actions"},
    {"id": "secret_identity", "name": "Secret Identity", "description": "A character concealing who they truly are"},
    {"id": "unlikely_allies", "name": "Unlikely Allies", "description": "Characters from opposing worlds or beliefs joining forces"},
    {"id": "obsession", "name": "Obsession", "description": "A character consumed by a singular fixation to destructive ends"},
]


def build_sample_context(job_id: str, query: str, n: int = 12) -> str:
    """Retrieve relevant chunks and format as context string."""
    chunks = retrieve_chunks(job_id, query, top_k=n)
    if not chunks:
        return "No relevant passages found."

    parts = []
    for i, c in enumerate(chunks):
        ref = c.get("page_reference", "")
        parts.append(f"[Passage {i+1} {ref}]\n{c['text']}")

    return "\n\n---\n\n".join(parts)


def passages_from_chunks(chunks: List[Dict]) -> List[SupportingPassage]:
    return [
        SupportingPassage(
            text=c["text"][:400] + ("..." if len(c["text"]) > 400 else ""),
            page_reference=c.get("page_reference"),
            relevance=f"Relevance score: {c.get('relevance_score', 0):.2f}",
        )
        for c in chunks[:3]
    ]


def analyze_overview(job_id: str, sample_text: str) -> NovelOverview:
    """Generate a novel overview using the first portions of the text."""
    prompt = f"""You are a skilled literary analyst. Based on the following opening passages from a novel, provide a structured overview.

Text sample:
{sample_text[:6000]}

Respond with a JSON object matching exactly this structure:
{{
  "title_guess": "your best guess at the title or 'Unknown'",
  "author_guess": "your best guess at the author or null",
  "genre_guess": "e.g. 'Gothic Romance', 'Literary Fiction', 'Fantasy', etc.",
  "setting_description": "where and when the story appears to take place",
  "narrative_summary": "2-3 sentence summary of what the novel appears to be about",
  "estimated_time_period": "e.g. '19th century England' or null if unclear",
  "point_of_view": "e.g. 'First-person', 'Third-person limited', 'Omniscient'",
  "tone": "e.g. 'Dark and brooding', 'Light and comedic', 'Melancholic'"
}}

Respond only with valid JSON."""

    response = client.chat.completions.create(
        model=settings.analysis_model,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.choices[0].message.content)
    return NovelOverview(**data)


def analyze_characters(job_id: str) -> List[CharacterAnalysis]:
    """Identify and analyze main characters."""
    # First pass: identify names
    context = build_sample_context(job_id, "main character protagonist name introduction", n=15)

    prompt = f"""You are an expert literary analyst performing character analysis on a novel.

Relevant passages:
{context}

Task: Identify the MAIN characters (not every named person — focus on characters with significant narrative presence). For each major character, provide detailed analysis.

Respond with a JSON array. Each element must match exactly:
{{
  "name": "Character's primary name",
  "aliases": ["list", "of", "nicknames", "or", "titles"],
  "role": "protagonist | antagonist | deuteragonist | supporting",
  "defining_traits": ["trait1", "trait2", "trait3"],
  "goals": ["what this character wants or seeks"],
  "conflicts": ["internal and external conflicts this character faces"],
  "important_relationships": ["Character X - nature of relationship"],
  "supporting_passages": [
    {{
      "text": "exact short quote or paraphrase from the text supporting this analysis",
      "page_reference": "p.X if known, otherwise null",
      "relevance": "why this passage supports the character analysis"
    }}
  ],
  "confidence": "high | moderate | low"
}}

Identify between 2-6 major characters. Focus on narrative significance, not just frequency of mention.
Return only valid JSON array."""

    response = client.chat.completions.create(
        model=settings.analysis_model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.choices[0].message.content)
    return [CharacterAnalysis(**c) for c in data]


def analyze_relationships(job_id: str, characters: List[CharacterAnalysis]) -> List[RelationshipAnalysis]:
    """Analyze relationships between major characters."""
    char_names = [c.name for c in characters]
    context = build_sample_context(job_id, f"relationship between {' '.join(char_names[:4])}", n=12)

    prompt = f"""You are an expert literary analyst examining character relationships in a novel.

Main characters identified: {', '.join(char_names)}

Relevant passages:
{context}

Task: Identify and analyze the KEY relationships between these characters. Focus on relationships that are narratively significant.

Valid relationship types: friendship, rivalry, romance, family, mentorship, alliance, conflict, complex

Respond with a JSON array. Each element must match:
{{
  "character_a": "Name of first character",
  "character_b": "Name of second character",
  "relationship_type": "one of the valid types above",
  "description": "1-2 sentence description of this relationship",
  "dynamics": "how the power/emotional dynamics work between them",
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase from text",
      "page_reference": "p.X or null",
      "relevance": "how this passage illustrates the relationship"
    }}
  ],
  "confidence": "high | moderate | low"
}}

Identify the most significant 3-8 relationships. Return only valid JSON array."""

    response = client.chat.completions.create(
        model=settings.analysis_model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.choices[0].message.content)
    relationships = []
    for r in data:
        # Validate relationship_type
        rt = r.get("relationship_type", "complex")
        try:
            r["relationship_type"] = RelationshipType(rt)
        except ValueError:
            r["relationship_type"] = RelationshipType.COMPLEX
        relationships.append(RelationshipAnalysis(**r))

    return relationships


def analyze_themes(job_id: str) -> List[ThemeAnalysis]:
    """Identify recurring themes and motifs."""
    context = build_sample_context(job_id, "theme motif recurring symbol meaning", n=15)

    prompt = f"""You are an expert literary analyst identifying themes and motifs in a novel.

Relevant passages:
{context}

Task: Identify the major themes and recurring motifs in this novel. A theme is a central idea; a motif is a recurring element (image, phrase, situation) that reinforces the theme.

Respond with a JSON array. Each element must match:
{{
  "theme": "Name of the theme (e.g., 'Loss and Grief', 'Power and Corruption')",
  "description": "2-3 sentence explanation of how this theme manifests in the novel",
  "motifs": ["recurring motif 1", "recurring motif 2"],
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase that illustrates this theme",
      "page_reference": "p.X or null",
      "relevance": "how this passage supports the theme interpretation"
    }}
  ],
  "prevalence": "central | significant | minor"
}}

Identify 3-6 themes. Use interpretive language like 'the text suggests', 'appears to explore'. Return only valid JSON array."""

    response = client.chat.completions.create(
        model=settings.analysis_model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.choices[0].message.content)
    return [ThemeAnalysis(**t) for t in data]


def analyze_tropes(job_id: str, characters: List[CharacterAnalysis]) -> List[TropeAnalysis]:
    """Detect tropes from predefined library."""
    char_summary = "; ".join([
        f"{c.name} ({c.role}): {', '.join(c.defining_traits[:3])}"
        for c in characters[:5]
    ])

    context = build_sample_context(job_id, "story structure conflict resolution journey", n=12)

    trope_list = "\n".join([
        f"- {t['id']}: {t['name']} — {t['description']}"
        for t in TROPE_LIBRARY
    ])

    prompt = f"""You are an expert literary analyst identifying narrative tropes in a novel.

Character summary: {char_summary}

Relevant passages:
{context}

Available trope library (use ONLY these trope IDs):
{trope_list}

Task: Identify which tropes from the library appear in this novel. You MUST identify multiple tropes (minimum 3, maximum 8). Each trope must be supported by textual evidence.

Respond with a JSON array. Each element must match:
{{
  "trope_name": "exact name from library",
  "trope_id": "exact id from library",
  "confidence": "strongly supported | moderately supported | weakly supported",
  "explanation": "2-3 sentences explaining how this trope appears in the text, using language like 'the text suggests' or 'evidence indicates'",
  "supporting_passages": [
    {{
      "text": "short quote or paraphrase from text",
      "page_reference": "p.X or null",
      "relevance": "how this illustrates the trope"
    }}
  ],
  "related_characters": ["Character names associated with this trope"]
}}

Return only valid JSON array."""

    response = client.chat.completions.create(
        model=settings.analysis_model,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    data = json.loads(response.choices[0].message.content)
    return [TropeAnalysis(**t) for t in data]


def run_full_analysis(job_id: str, pages: List[Tuple[int, str]]) -> AnalysisReport:
    """Run the complete literary analysis pipeline."""
    logger.info(f"Starting full analysis for job {job_id}")

    # Get sample text for overview
    sample_pages = pages[:20]
    sample_text = "\n\n".join([text for _, text in sample_pages])

    # Run analyses
    logger.info("Analyzing overview...")
    overview = analyze_overview(job_id, sample_text)

    logger.info("Analyzing characters...")
    characters = analyze_characters(job_id)

    logger.info("Analyzing relationships...")
    relationships = analyze_relationships(job_id, characters)

    logger.info("Analyzing themes...")
    themes = analyze_themes(job_id)

    logger.info("Analyzing tropes...")
    tropes = analyze_tropes(job_id, characters)

    report = AnalysisReport(
        job_id=job_id,
        overview=overview,
        characters=characters,
        relationships=relationships,
        themes=themes,
        tropes=tropes,
        created_at=datetime.now(timezone.utc),
    )

    logger.info(f"Analysis complete for job {job_id}")
    return report
