"""
Literary analysis service using an agentic tool-use loop.

Architecture change (v2): Instead of calling LLM functions directly in sequence,
this module exposes a coordinator that uses Groq's function-calling API (OpenAI-
compatible format, equivalent to Anthropic's tool_use pattern) to let the model
decide which analysis tools to call and in what order.

Each tool retrieves fresh, task-specific passages from ChromaDB rather than
sharing a single context block — this gives each analysis step the most relevant
evidence.

A tool_calls_log is collected and stored in the AnalysisReport for observability.
Falls back to direct sequential calls if the agentic loop fails for any tool.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from groq import Groq

from app.core.config import settings
from app.models.schemas import (
    AnalysisReport,
    CharacterAnalysis,
    NovelOverview,
    RelationshipAnalysis,
    RelationshipType,
    SupportingPassage,
    ThemeAnalysis,
    TropeAnalysis,
)
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)


# ── JSON parsing helpers ──────────────────────────────────────────────────────

def parse_json_response(content: str) -> Any:
    """Parse JSON from LLM response, stripping markdown fences and recovering truncated arrays."""
    if not content or not content.strip():
        raise ValueError("Empty response from LLM")
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for start_char, end_char in [("[", "]"), ("{", "}")]:
            start = text.find(start_char)
            end = text.rfind(end_char)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        raise


def llm_call_with_retry(
    prompt: str, model: str, max_tokens: int, max_attempts: int = 3
) -> Any:
    """Call the LLM and parse JSON, retrying on malformed responses."""
    last_error: Exception = ValueError("No attempts made")
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return parse_json_response(response.choices[0].message.content)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning(f"JSON parse failed on attempt {attempt}/{max_attempts}: {e}")
    raise ValueError(f"LLM returned invalid JSON after {max_attempts} attempts: {last_error}")


# ── Trope library ─────────────────────────────────────────────────────────────

TROPE_LIBRARY = [
    # ── Classic / literary tropes ────────────────────────────────────────────
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
    # ── Love triangles ─────────────────────────────────────────────────────
    {"id": "sibling_triangle", "name": "Sibling Triangle", "description": "A love triangle in which two of the three participants are siblings"},
    {"id": "best_friend_triangle", "name": "Best Friend Triangle", "description": "A love triangle involving a protagonist and their best friend as rivals"},
    {"id": "betty_and_veronica_triangle", "name": "Betty & Veronica Triangle", "description": "A protagonist choosing between a safe familiar love and an exciting dangerous one"},
    {"id": "tug_of_war_triangle", "name": "Tug-of-war Triangle", "description": "Two love interests who openly compete for a protagonist's affection"},
    # ── Marriage and commitment ────────────────────────────────────────────
    {"id": "arranged_marriage", "name": "Arranged Marriage", "description": "Partners brought together by family or social obligation rather than romantic choice"},
    {"id": "marriage_pact", "name": "Marriage Pact", "description": "Two friends agree to marry each other if still single by a certain age"},
    {"id": "marriage_before_romance", "name": "Marriage Before Romance", "description": "Characters who marry for practical reasons before falling genuinely in love"},
    {"id": "jilted_bride", "name": "Jilted Bride", "description": "A character left at the altar who must rebuild their life"},
    {"id": "altar_diplomacy", "name": "Altar Diplomacy", "description": "A marriage arranged for political, dynastic, or strategic reasons"},
    # ── Fake and secret relationships ─────────────────────────────────────
    {"id": "fake_relationship", "name": "Fake Relationship", "description": "Characters pretend to be in a relationship for social purposes and develop genuine feelings"},
    {"id": "secret_relationship", "name": "Secret Relationship", "description": "A couple who must hide their romance from the world around them"},
    {"id": "the_bet", "name": "The Bet", "description": "Characters make a wager involving romantic conquest, only to develop real feelings"},
    {"id": "revenge_romance", "name": "Revenge Romance", "description": "A character pursues romance as part of a revenge scheme but falls genuinely in love"},
    # ── Friends-to-lovers and reunion ─────────────────────────────────────
    {"id": "friends_to_lovers", "name": "Friends to Lovers", "description": "A deep friendship that slowly evolves into romantic love"},
    {"id": "childhood_friends_reunion", "name": "Childhood Friends Reunion", "description": "Former childhood friends who reconnect as adults and discover romantic feelings"},
    {"id": "second_chance_romance", "name": "Second Chance Romance", "description": "Former lovers who reunite and get another chance"},
    {"id": "return_to_hometown", "name": "Return to Hometown", "description": "A character returning home encounters a past love"},
    # ── Enemies and rivals ────────────────────────────────────────────────
    {"id": "enemies_to_lovers", "name": "Enemies to Lovers", "description": "Characters who begin as genuine antagonists and gradually fall in love"},
    {"id": "rivals", "name": "Rivals", "description": "Direct competitors whose rivalry masks and fuels mutual attraction"},
    {"id": "love_hate", "name": "Love/Hate", "description": "A relationship that oscillates between fierce conflict and fierce romance"},
    {"id": "bully_romance", "name": "Bully Romance", "description": "A former bully and their target develop complicated romantic feelings"},
    # ── Workplace and class ───────────────────────────────────────────────
    {"id": "office_romance_coworkers", "name": "Office Romance: Coworkers", "description": "Colleagues who develop romantic feelings while working together"},
    {"id": "sleeping_with_boss", "name": "Sleeping with the Boss", "description": "A romance between an employee and their professional superior"},
    {"id": "social_class_conflict", "name": "Class Conflict", "description": "Tension between characters of different social or economic strata"},
    {"id": "rich_and_poor", "name": "The Rich and the Poor", "description": "A romance that bridges extreme economic inequality"},
    # ── Character archetypes ──────────────────────────────────────────────
    {"id": "tortured_hero", "name": "Tortured Hero", "description": "A protagonist burdened by trauma, guilt, or profound inner darkness"},
    {"id": "alpha_hero", "name": "Alpha Hero / Antihero", "description": "A dominant, morally complex hero who is irresistible despite his flaws"},
    {"id": "grumpy_sunshine", "name": "Grumpy/Sunshine", "description": "A brooding character who falls for an optimistic, relentlessly cheerful one"},
    {"id": "bad_boy_good_girl", "name": "Bad Boy / Good Girl", "description": "A rebellious character who falls for a wholesome, virtuous one"},
    {"id": "wallflower", "name": "Wallflower", "description": "A shy, overlooked character who is truly seen and loved by exactly the right person"},
    {"id": "ugly_duckling", "name": "The Ugly Duckling", "description": "A character undergoes a transformation that changes how others perceive them"},
    # ── Fairy tale and fantasy ────────────────────────────────────────────
    {"id": "cinderella_circumstance", "name": "Cinderella Circumstance", "description": "A character of humble origins elevated through love and circumstance"},
    {"id": "beauty_and_the_beast", "name": "Beauty and the Beast", "description": "A character who falls for someone initially perceived as monstrous"},
    {"id": "fairytale_retelling", "name": "Fairytale Retelling", "description": "A story retelling or inspired by a classic fairy tale"},
    {"id": "time_travel", "name": "Time Travel", "description": "A romance complicated by travel across different time periods"},
    {"id": "soulmates_destined", "name": "Destined to Be Together", "description": "Characters believed by fate to be meant for each other"},
    # ── Proximity and circumstance ────────────────────────────────────────
    {"id": "roommate_romance", "name": "Roommate Romance", "description": "Housemates who share space and gradually fall in love"},
    {"id": "road_trip_romance", "name": "Road Trip Romance", "description": "Love sparked or deepened during a shared journey"},
    {"id": "stranded", "name": "Stranded", "description": "Characters isolated together who develop romantic feelings"},
    {"id": "military_romance", "name": "Military Romance", "description": "A romance set against the backdrop of military service or conflict"},
    # ── Emotional barriers ────────────────────────────────────────────────
    {"id": "sworn_off_relationship", "name": "Sworn Off Relationships", "description": "A character who has vowed to avoid romance is swept irresistibly off their feet"},
    {"id": "lovers_in_denial", "name": "Lovers in Denial", "description": "Characters who refuse to acknowledge their obvious mutual romantic feelings"},
    {"id": "emotional_scars", "name": "Emotional Scars", "description": "Characters whose past trauma shapes their capacity and fear of love"},
    {"id": "belated_love_epiphany", "name": "Belated Love Epiphany", "description": "A character realizes — almost too late — that they are truly in love"},
    # ── Loss and new beginnings ───────────────────────────────────────────
    {"id": "widow_widower", "name": "Widow/Widower", "description": "A bereaved character who finds unexpected new love after profound loss"},
    {"id": "found_family", "name": "Found Family", "description": "Characters forming deep familial bonds outside biological family"},
    {"id": "injury_recovery", "name": "Injury/Illness Recovery", "description": "A romance that deepens through one character caring for an injured other"},
    # ── Hidden truths ─────────────────────────────────────────────────────
    {"id": "secret_heir", "name": "Secret/Lost Heir", "description": "A character discovers they are heir to a significant legacy"},
    {"id": "everyone_can_see_it", "name": "Everyone Can See It", "description": "The romantic tension between two people is obvious to everyone but the pair"},
    {"id": "mistaken_identity", "name": "Mistaken Identity", "description": "A character mistaken for someone else becomes entangled in an unintended romance"},
    {"id": "undercover_love", "name": "Undercover Love", "description": "A character working undercover develops genuine romantic feelings"},
]

_ROMANCE_KEYWORDS = {"romance", "love", "romantic", "contemporary romance", "historical romance",
                     "paranormal romance", "dark romance", "erotic", "chick lit", "women's fiction"}
_FANTASY_KEYWORDS = {"fantasy", "magic", "supernatural", "paranormal", "urban fantasy",
                     "epic fantasy", "high fantasy", "fairy", "myth"}
_THRILLER_KEYWORDS = {"thriller", "mystery", "crime", "suspense", "detective", "noir", "horror"}

MAX_TROPES_IN_PROMPT = 90


def _select_tropes_for_genre(job_id: str, genre: str) -> List[Dict]:
    import random
    genre_lower = genre.lower()
    classic = TROPE_LIBRARY[:25]
    rest = TROPE_LIBRARY[25:]
    is_romance = any(k in genre_lower for k in _ROMANCE_KEYWORDS)
    rng = random.Random(job_id)
    slots = MAX_TROPES_IN_PROMPT - len(classic)
    if is_romance:
        selected_rest = rng.sample(rest, min(slots, len(rest)))
    else:
        selected_rest = rng.sample(rest, min(slots, len(rest)))
    return classic + selected_rest


# ── Context helpers ───────────────────────────────────────────────────────────

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


# ── Individual analysis functions (used both directly and as tool implementations) ──

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
    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=1000)
    return NovelOverview(**data)


def analyze_characters(job_id: str) -> List[CharacterAnalysis]:
    """Identify and analyze main characters."""
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
    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2500)
    return [CharacterAnalysis(**c) for c in data]


def analyze_relationships(
    job_id: str, characters: List[CharacterAnalysis]
) -> List[RelationshipAnalysis]:
    """Analyze relationships between major characters."""
    char_names = [c.name for c in characters]
    context = build_sample_context(
        job_id, f"relationship between {' '.join(char_names[:4])}", n=12
    )
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
    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    relationships = []
    for r in data:
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
    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    return [ThemeAnalysis(**t) for t in data]


def analyze_tropes(
    job_id: str,
    characters: List[CharacterAnalysis],
    overview: Optional[NovelOverview] = None,
) -> List[TropeAnalysis]:
    """Detect tropes from predefined library using genre-aware trope selection."""
    char_summary = "; ".join([
        f"{c.name} ({c.role}): {', '.join(c.defining_traits[:3])}"
        for c in characters[:5]
    ])
    genre = overview.genre_guess if overview else "unknown"
    novel_summary = overview.narrative_summary if overview else ""

    context_structure = build_sample_context(
        job_id, "story structure conflict resolution character arc", n=8
    )
    context_relationships = build_sample_context(
        job_id,
        f"romance relationship love conflict {' '.join([c.name for c in characters[:3]])}",
        n=8,
    )
    context = f"{context_structure}\n\n---\n\n{context_relationships}"

    selected = _select_tropes_for_genre(job_id, genre)
    trope_list = "\n".join([
        f"- {t['id']}: {t['name']} — {t['description']}" for t in selected
    ])

    prompt = f"""You are an expert literary analyst identifying narrative tropes in a novel.

Genre: {genre}
Novel summary: {novel_summary}
Character summary: {char_summary}

Relevant passages:
{context}

Available trope library (use ONLY these trope IDs):
{trope_list}

Task: Identify which tropes from the library appear in this novel. Prioritise tropes that match the genre and are directly supported by the passages above. You MUST identify multiple tropes (minimum 3, maximum 8).

Respond with a JSON array. Each element must match:
{{
  "trope_name": "exact name from library",
  "trope_id": "exact id from library",
  "confidence": "strongly supported | moderately supported | weakly supported",
  "explanation": "2-3 sentences explaining how this trope appears in the text",
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
    data = llm_call_with_retry(prompt, settings.analysis_model, max_tokens=2000)
    return [TropeAnalysis(**t) for t in data]


# ── Agentic tool definitions (Groq/OpenAI-compatible function-calling format) ──
# Input schemas follow the same structure as Anthropic's tool_use format.

ANALYSIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_overview",
            "description": "Generate a structured overview of the novel: title, author, genre, setting, summary, POV, and tone. Call this first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retrieval_hint": {
                        "type": "string",
                        "description": "Ignored — overview uses the raw opening text directly.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "identify_characters",
            "description": "Identify and analyse the 2–6 major characters with traits, goals, conflicts, and supporting passages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retrieval_hint": {
                        "type": "string",
                        "description": "Optional override query for passage retrieval (default: protagonist names).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_themes",
            "description": "Identify 3–6 major themes and their motifs with textual evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retrieval_hint": {
                        "type": "string",
                        "description": "Optional override query for passage retrieval.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_relationships",
            "description": "Map 3–8 key character relationships. Requires identify_characters to have been called first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retrieval_hint": {
                        "type": "string",
                        "description": "Optional override query for passage retrieval.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_tropes",
            "description": "Detect 3–8 narrative tropes from the predefined library. Requires generate_overview and identify_characters to have been called first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "retrieval_hint": {
                        "type": "string",
                        "description": "Optional override query for passage retrieval.",
                    }
                },
                "required": [],
            },
        },
    },
]

_ALL_TOOL_NAMES = {t["function"]["name"] for t in ANALYSIS_TOOLS}


def _execute_tool(
    name: str,
    job_id: str,
    pages: List[Tuple[int, str]],
    accumulated: Dict[str, Any],
) -> Any:
    """Dispatch a tool call to the corresponding analysis function."""
    if name == "generate_overview":
        sample_text = "\n\n".join([text for _, text in pages[:20]])
        return analyze_overview(job_id, sample_text)

    elif name == "identify_characters":
        return analyze_characters(job_id)

    elif name == "detect_themes":
        return analyze_themes(job_id)

    elif name == "analyze_relationships":
        chars = accumulated.get("identify_characters") or []
        if not chars:
            # Fallback: run character analysis first if coordinator skipped it
            chars = analyze_characters(job_id)
            accumulated["identify_characters"] = chars
        return analyze_relationships(job_id, chars)

    elif name == "detect_tropes":
        chars = accumulated.get("identify_characters") or []
        if not chars:
            chars = analyze_characters(job_id)
            accumulated["identify_characters"] = chars
        overview = accumulated.get("generate_overview")
        return analyze_tropes(job_id, chars, overview)

    else:
        raise ValueError(f"Unknown tool: {name}")


def run_full_analysis(
    job_id: str, pages: List[Tuple[int, str]]
) -> AnalysisReport:
    """
    Run the complete literary analysis using an agentic tool-use loop.

    The Groq coordinator model decides which tools to call and in what order.
    Results from earlier tools (characters, overview) are made available to
    later tools (relationships, tropes) via the accumulated dict.

    Falls back to direct sequential calls for any tool the loop misses.
    """
    logger.info(f"Starting agentic analysis for job {job_id}")

    tool_calls_log: List[Dict] = []
    accumulated: Dict[str, Any] = {}
    sample_text = "\n\n".join([text for _, text in pages[:20]])

    # ── Coordinator prompt ─────────────────────────────────────────────────
    system_prompt = (
        "You are a literary analysis coordinator. Orchestrate a complete analysis of a novel "
        "by calling all five available tools. Required call order:\n"
        "1. generate_overview\n"
        "2. identify_characters\n"
        "3. detect_themes\n"
        "4. analyze_relationships  (needs identify_characters result)\n"
        "5. detect_tropes          (needs generate_overview + identify_characters)\n\n"
        "Call ALL five tools. Do not produce text output — only tool calls."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Analyse this novel. Opening text (first 3000 chars):\n\n"
                f"{sample_text[:3000]}\n\n"
                "Please call all five analysis tools now."
            ),
        },
    ]

    MAX_ITERATIONS = 12
    for iteration in range(MAX_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=settings.analysis_model,
                messages=messages,
                tools=ANALYSIS_TOOLS,
                tool_choice="auto",
                max_tokens=256,
            )
        except Exception as e:
            logger.warning(f"Coordinator call failed at iteration {iteration}: {e}")
            break

        choice = response.choices[0]

        # Build assistant message for history
        asst_msg: Dict[str, Any] = {"role": "assistant", "content": choice.message.content or ""}
        if choice.message.tool_calls:
            asst_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]
        messages.append(asst_msg)

        if choice.finish_reason == "stop" or not choice.message.tool_calls:
            break

        # Execute each requested tool call
        for tc in choice.message.tool_calls:
            tool_name = tc.function.name
            if tool_name not in _ALL_TOOL_NAMES:
                logger.warning(f"Coordinator requested unknown tool: {tool_name}")
                continue

            if tool_name in accumulated:
                # Already ran — skip duplicate and tell coordinator
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"status": "already_completed"}),
                })
                continue

            logger.info(f"Executing tool: {tool_name} (iteration {iteration})")
            t_start = time.monotonic()
            try:
                result = _execute_tool(tool_name, job_id, pages, accumulated)
                accumulated[tool_name] = result
                duration = round(time.monotonic() - t_start, 2)
                tool_calls_log.append(
                    {
                        "tool": tool_name,
                        "iteration": iteration,
                        "duration_s": duration,
                        "success": True,
                        "items": len(result) if isinstance(result, list) else 1,
                    }
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(
                        {"status": "ok", "items": len(result) if isinstance(result, list) else 1}
                    ),
                })
            except Exception as e:
                duration = round(time.monotonic() - t_start, 2)
                logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
                tool_calls_log.append(
                    {"tool": tool_name, "iteration": iteration, "duration_s": duration, "success": False, "error": str(e)}
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"status": "error", "error": str(e)}),
                })

        # Stop early if all tools have been called
        if _ALL_TOOL_NAMES.issubset(accumulated.keys()):
            logger.info("All tools completed — stopping agentic loop early")
            break

    # ── Fill in any tools the coordinator missed (fallback) ───────────────
    if "generate_overview" not in accumulated:
        logger.info("Fallback: running generate_overview directly")
        accumulated["generate_overview"] = analyze_overview(job_id, sample_text)
        tool_calls_log.append({"tool": "generate_overview", "iteration": -1, "fallback": True})

    if "identify_characters" not in accumulated:
        logger.info("Fallback: running identify_characters directly")
        accumulated["identify_characters"] = analyze_characters(job_id)
        tool_calls_log.append({"tool": "identify_characters", "iteration": -1, "fallback": True})

    if "detect_themes" not in accumulated:
        logger.info("Fallback: running detect_themes directly")
        accumulated["detect_themes"] = analyze_themes(job_id)
        tool_calls_log.append({"tool": "detect_themes", "iteration": -1, "fallback": True})

    if "analyze_relationships" not in accumulated:
        logger.info("Fallback: running analyze_relationships directly")
        chars = accumulated["identify_characters"]
        accumulated["analyze_relationships"] = analyze_relationships(job_id, chars)
        tool_calls_log.append({"tool": "analyze_relationships", "iteration": -1, "fallback": True})

    if "detect_tropes" not in accumulated:
        logger.info("Fallback: running detect_tropes directly")
        chars = accumulated["identify_characters"]
        overview = accumulated.get("generate_overview")
        accumulated["detect_tropes"] = analyze_tropes(job_id, chars, overview)
        tool_calls_log.append({"tool": "detect_tropes", "iteration": -1, "fallback": True})

    # ── Assemble final report ─────────────────────────────────────────────
    report = AnalysisReport(
        job_id=job_id,
        overview=accumulated["generate_overview"],
        characters=accumulated["identify_characters"],
        relationships=accumulated["analyze_relationships"],
        themes=accumulated["detect_themes"],
        tropes=accumulated["detect_tropes"],
        created_at=datetime.now(timezone.utc),
        tool_calls_log=tool_calls_log,
    )

    logger.info(
        f"Analysis complete for job {job_id} — "
        f"{len(tool_calls_log)} tool calls, "
        f"{sum(1 for t in tool_calls_log if t.get('success', True) and not t.get('fallback'))} via agent"
    )
    return report
