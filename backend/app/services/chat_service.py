from groq import Groq
import logging
from typing import List, Dict
from app.core.config import settings
from app.models.schemas import ChatMessage, ChatResponse, SupportingPassage
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)


def _build_retrieval_query(message: str, history: List[ChatMessage]) -> str:
    """Combine the current message with recent history to form a self-contained retrieval query.

    Follow-up questions like "what happened next?" are useless for retrieval on their own.
    Prepending the last assistant turn and prior user turn gives the embedder enough context
    to find the right chunks.
    """
    if not history:
        return message

    # Take the last user + assistant exchange (up to 2 prior turns)
    recent: List[str] = []
    for msg in history[-4:]:
        if msg.role == "user":
            recent.append(f"User asked: {msg.content}")
        elif msg.role == "assistant":
            # Only include the first sentence of the assistant reply to keep query short
            first_sentence = msg.content.split(".")[0].strip()
            recent.append(f"Assistant said: {first_sentence}")

    context_prefix = " | ".join(recent)
    return f"{context_prefix} | Current question: {message}"


def chat_with_novel(
    job_id: str,
    message: str,
    history: List[ChatMessage],
    analysis_summary: str = "",
) -> ChatResponse:
    """Answer a user's question about the novel using RAG."""

    # Build a context-aware retrieval query from history + current message
    retrieval_query = _build_retrieval_query(message, history)
    chunks = retrieve_chunks(job_id, retrieval_query, top_k=settings.top_k_chunks)

    # Build context block
    context_parts = []
    for i, c in enumerate(chunks):
        ref = c.get("page_reference", "")
        context_parts.append(f"[Source {i+1} {ref}]\n{c['text']}")

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant passages found."

    system_prompt = f"""You are a literary analyst assistant helping a reader understand a novel they have uploaded to StoryScope.

You have been given passages retrieved directly from the novel that are relevant to the user's question. Your job is to answer using ONLY what those passages say.

Rules:
- Answer from the retrieved passages. Quote or paraphrase with page references (e.g. "p.12") whenever possible.
- If the passages do not contain enough information to answer, say so explicitly: "The retrieved passages don't directly cover this."
- Never invent plot details, character names, or events not present in the passages.
- Use interpretive language: "the text suggests", "based on p.X", "evidence indicates".
- Be conversational but precise. Prefer short, direct answers over lengthy analysis unless asked.
- If the question is a follow-up ("what happened next?", "why did she do that?"), interpret it in light of the conversation so far.

Novel analysis summary (use as background context only — always prefer the retrieved passages):
{analysis_summary[:1500] if analysis_summary else "Not yet available."}

Retrieved passages:
{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=settings.chat_model,
        max_tokens=1000,
        messages=messages,
    )

    response_text = response.choices[0].message.content

    if not chunks:
        confidence = "low"
    elif len(chunks) >= 5:
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
