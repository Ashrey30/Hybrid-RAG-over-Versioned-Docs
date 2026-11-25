import re


_CAPABILITY_QUESTIONS = {
    "what can you help me with",
    "what can you help with",
    "what can you do",
    "what can i ask you",
    "what questions can i ask you",
    "what are your capabilities",
    "who are you",
    "what are you",
}

_CAPABILITY_ANSWER = (
    "I can answer questions using the documents indexed in this app, explain concepts, and compare "
    "information across them. I can also help with basic general-knowledge questions; document-based "
    "answers include citations."
)


def capability_answer(question: str) -> str | None:
    """Return a deterministic response for common assistant-capability questions."""
    normalized = re.sub(r"[^\w\s]", "", question.casefold())
    normalized = " ".join(normalized.split())
    return _CAPABILITY_ANSWER if normalized in _CAPABILITY_QUESTIONS else None


SYSTEM_RAG = (
    "You answer questions using the supplied document context when the question is about those documents "
    "or their domain-specific details. For those questions, use ONLY relevant context, cite every factual "
    "claim with its supporting chunk ID in square brackets (for example [a1b2c3d4e5]), and never cite an "
    "ID that is not in the context. If relevant context does not contain the answer, reply exactly: I don't know. "
    "Do not use outside knowledge to answer document-specific questions. "
    "For greetings, thanks, acknowledgments, questions about what you can help with, and simple general-knowledge "
    "questions that are not asking about the documents or their domain-specific details, answer briefly without "
    "citations and ignore unrelated retrieved context. "
    "If asked to repeat or simplify a previous answer that is not included in the current request, ask the user "
    "to paste that answer. Write in clear, polished prose with complete sentences. Start with a direct answer, "
    "then include the supporting detail needed to fully address the question. Use brief, organized bullets for "
    "multi-part or procedural answers. Do not repeat the question, output Markdown links, or include raw URLs; "
    "use the required chunk citations instead. Avoid filler and unsupported detail."
)

SYSTEM_NO_CONTEXT = (
    "You are the assistant of a document Q&A system. No documentation was retrieved for this message. "
    "Reply briefly to greetings, thanks, acknowledgments, capability questions, and simple general-knowledge "
    "questions. If asked to repeat or simplify a previous answer that is not included in the current request, "
    "ask the user to paste that answer. If the question needs details from the project's documents, reply exactly: "
    "I don't know. Keep other answers clear, polished, and direct, without Markdown links or raw URLs."
)


MAX_CONTEXT_CHARS = 16000   # keeps a request under Groq's 7,000 input-token limit (code is token-dense)


def build_context(hits, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Join chunks, truncating the last one that does not fit in the character budget."""
    parts, used = [], 0
    for h in hits:
        piece = f"[{h.chunk_id}] {h.payload['text']}"
        if used + len(piece) > max_chars:
            room = max_chars - used
            if room > 300:
                parts.append(piece[:room] + " ...")
            break
        parts.append(piece)
        used += len(piece) + 2
    return "\n\n".join(parts)


def build_prompt(question: str, hits, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, str]:
    """Returns (system, user)."""
    if not hits:
        return SYSTEM_NO_CONTEXT, f"Question: {question}\nAnswer:"
    return SYSTEM_RAG, f"Context:\n{build_context(hits, max_chars)}\n\nQuestion: {question}\nAnswer:"
