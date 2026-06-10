"""
RAG chat service for StoryScope.

Two entry points are provided:
  chat_with_novel()        — original synchronous response (kept for compatibility)
  stream_chat_with_novel() — SSE generator for streaming responses

Streaming uses Groq's OpenAI-compatible stream=True flag. Sources (retrieved
passages) are emitted as the first SSE event so the frontend can display them
before the full response arrives.

SSE event format:
  data: {"type": "sources", "sources": [...]}  — first event
  data: {"type": "token",   "token": "...", "done": false}  — per token
  data: {"type": "done",    "done": true}  — final event
"""
from __future__ import annotations

import json
import logging
from typing import Generator, List

from groq import Groq

from app.core.config import settings
from app.models.schemas import ChatMessage, ChatResponse, SupportingPassage
from app.services.embedding_service import retrieve_chunks

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.groq_api_key)


def _build_retrieval_query(message: str, history: List[ChatMessage]) -> str:
    """Combine the current message with recent history to form a self-contained retrieval query.

    Follow-up questions like 'what happened next?' are useless for retrieval on their own.
    Prepending the last assistant turn and prior user turn gives the embedder enough context
    to find the right chunks.
    """
    if not history:
        return message

    recent: List[str] = []
    for msg in history[-4:]:
        if msg.role == "user":
            recent.append(f"User asked: {msg.content}")
        elif msg.role == "assistant":
            first_sentence = msg.content.split(".")[0].strip()
            recent.append(f"Assistant said: {first_sentence}")

    context_prefix = " | ".join(recent)
    return f"{context_prefix} | Current question: {message}"


def _build_chat_context(
    job_id: str,
    message: str,
    history: List[ChatMessage],
    analysis_summary: str,
) -> tuple[list, list[SupportingPassage]]:
    """Retrieve passages and build the messages list for the LLM.

    Returns (messages_list, sources) so both sync and streaming paths share logic.
    """
    retrieval_query = _build_retrieval_query(message, history)
    chunks = retrieve_chunks(job_id, retrieval_query, top_k=settings.top_k_chunks)

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

    messages: list = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    sources = [
        SupportingPassage(
            text=c["text"][:300] + ("..." if len(c["text"]) > 300 else ""),
            page_reference=c.get("page_reference"),
            relevance=f"Retrieved for: {message[:50]}",
        )
        for c in chunks[:3]
    ]

    return messages, sources


def chat_with_novel(
    job_id: str,
    message: str,
    history: List[ChatMessage],
    analysis_summary: str = "",
) -> ChatResponse:
    """Answer a user's question about the novel using RAG (non-streaming)."""
    messages, sources = _build_chat_context(job_id, message, history, analysis_summary)

    response = client.chat.completions.create(
        model=settings.chat_model,
        max_tokens=1000,
        messages=messages,
    )
    response_text = response.choices[0].message.content

    confidence = "low" if not sources else ("high" if len(sources) >= 3 else "moderate")
    return ChatResponse(response=response_text, sources=sources, confidence=confidence)


def stream_chat_with_novel(
    job_id: str,
    message: str,
    history: List[ChatMessage],
    analysis_summary: str = "",
) -> Generator[str, None, None]:
    """Stream a chat response as SSE events.

    Yields:
        SSE-formatted strings that FastAPI's StreamingResponse passes directly
        to the client. The caller must set media_type="text/event-stream".
    """
    messages, sources = _build_chat_context(job_id, message, history, analysis_summary)

    # Emit sources first so the UI can display them before text arrives.
    sources_payload = [s.model_dump() for s in sources]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload})}\n\n"

    try:
        stream = client.chat.completions.create(
            model=settings.chat_model,
            max_tokens=1000,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            token = delta.content if delta and delta.content else ""
            if token:
                yield f"data: {json.dumps({'type': 'token', 'token': token, 'done': False})}\n\n"

    except Exception as e:
        logger.error(f"Streaming error for job {job_id}: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    finally:
        yield f"data: {json.dumps({'type': 'done', 'done': True})}\n\n"
