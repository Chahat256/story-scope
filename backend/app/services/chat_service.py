import anthropic
import logging
from typing import List, Dict
from app.core.config import settings
from app.models.schemas import ChatMessage, ChatResponse, SupportingPassage
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def chat_with_novel(
    job_id: str,
    message: str,
    history: List[ChatMessage],
    analysis_summary: str = "",
) -> ChatResponse:
    """Answer a user's question about the novel using RAG."""

    # Retrieve relevant chunks
    chunks = retrieve_chunks(job_id, message, top_k=settings.top_k_chunks)

    # Build context
    context_parts = []
    for i, c in enumerate(chunks):
        ref = c.get("page_reference", "")
        context_parts.append(f"[Source {i+1} {ref}]\n{c['text']}")

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant passages found."

    # Build system prompt
    system_prompt = f"""You are a literary analyst assistant helping a reader understand a novel they've uploaded to StoryScope.

You have access to relevant passages from the novel retrieved for the user's question. Base your answers on these passages.

Important guidelines:
- Ground your answers in the retrieved passages. Quote or paraphrase them with page references when relevant.
- If the retrieved passages don't support an answer, say so clearly rather than speculating.
- Use interpretive language: "the text suggests", "based on the passages", "evidence indicates"
- Do not fabricate plot details or character information not supported by the passages.
- Be conversational but analytically precise.
- If asked about something not covered in the retrieved passages, say: "The retrieved passages don't directly address this. Based on what I can see..."

Analysis context (summary of the novel analysis):
{analysis_summary[:2000] if analysis_summary else "Analysis not yet available."}

Retrieved passages relevant to the user's question:
{context}"""

    # Build message history
    messages = []
    for msg in history[-6:]:  # Keep last 6 turns for context
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    response = client.messages.create(
        model=settings.chat_model,
        max_tokens=1500,
        system=system_prompt,
        messages=messages,
    )

    response_text = response.content[0].text

    # Determine confidence based on chunk availability
    if not chunks:
        confidence = "low"
    elif len(chunks) >= 3:
        confidence = "high"
    else:
        confidence = "moderate"

    sources = [
        SupportingPassage(
            text=c["text"][:300] + ("..." if len(c["text"]) > 300 else ""),
            page_reference=c.get("page_reference"),
            relevance=f"Retrieved for: {message[:50]}",
        )
        for c in chunks[:3]
    ]

    return ChatResponse(
        response=response_text,
        sources=sources,
        confidence=confidence,
    )
