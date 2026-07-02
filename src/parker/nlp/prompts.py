"""Prompt templates for LLM-based debate transcript extraction.

Two-pass extraction:
  Pass 1: Keywords + Topics (KEYWORD_TOPIC_SYSTEM_PROMPT)
  Pass 2: Stances per speaker per topic (STANCE_SYSTEM_PROMPT)
"""

from parker.models import Debate, Utterance

KEYWORD_TOPIC_SYSTEM_PROMPT = """\
You are an expert political debate analyst. Your task is to extract keywords and topics \
from a debate transcript between a host ("parker") and a caller.

Instructions:
- Extract notable keywords and phrases used by each speaker ("parker" or "caller").
- For each keyword, note the speaker who used it and the approximate number of times it appeared.
- Extract the main topics discussed in the debate. Each topic should be a short label (3-8 words) \
with a one-sentence description.
- If a list of existing topics is provided, reuse them when semantically equivalent instead of \
creating duplicates. Only create a new topic if it is genuinely distinct.
- Filter out common debate filler words (well, look, so, um, uh, like, actually, basically, etc.).
- Focus on substantive arguments, policy positions, and factual claims — not meta-discussion \
about the debate itself (e.g., ignore "let me finish" or "that's a good point").
- Keywords should capture the speaker's distinctive language, rhetorical devices, and talking points.

Return structured JSON matching the provided schema exactly.\
"""

STANCE_SYSTEM_PROMPT = """\
You are an expert political debate analyst. Your task is to classify each speaker's stance \
on the given topics from a debate transcript.

Instructions:
- For each topic and each speaker ("parker" or "caller"), classify the stance as one of:
  - SUPPORTS: Speaker clearly advocates for or agrees with the topic/position.
  - OPPOSES: Speaker clearly argues against or disagrees with the topic/position.
  - QUALIFIED: Speaker has a nuanced or conditional position (e.g., "I support X but only if Y").
  - DEFLECTS: Speaker avoids taking a clear position, redirects, or changes the subject.
- Include a confidence score:
  - 0.9+ for explicit, unambiguous statements.
  - 0.5-0.7 for inferred positions based on context and implication.
  - Below 0.5 for highly ambiguous or unclear positions.
- Include brief evidence: a short quote or paraphrase from the transcript supporting \
your classification.
- Debate language is inherently combative — do not confuse aggressive tone with opposition \
to a topic. A speaker can aggressively SUPPORT something.
- Every speaker-topic combination must have exactly one stance entry.

Return structured JSON matching the provided schema exactly.\
"""


def format_transcript_for_llm(debate: Debate, utterances: list[Utterance]) -> str:
    """Format a debate transcript for LLM consumption.

    Output format:
        Debate: {title}
        URL: {url}

        [MM:SS] SPEAKER: text here
        ...
    """
    lines = [
        f"Debate: {debate.title}",
        f"URL: {debate.url}",
        "",
    ]
    for u in utterances:
        mins = int(u.start_time // 60)
        secs = int(u.start_time % 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {u.speaker.upper()}: {u.text}")

    return "\n".join(lines)


def build_keyword_topic_messages(
    transcript_text: str, existing_topics: list[str]
) -> list[dict]:
    """Build the messages list for Pass 1 (keyword + topic extraction).

    If existing_topics is non-empty, appends them to the user message so the LLM
    can reuse semantically equivalent topics instead of creating duplicates.
    """
    user_content = f"Analyze this debate transcript:\n\n{transcript_text}"

    if existing_topics:
        topic_list = ", ".join(existing_topics)
        user_content += (
            f"\n\nExisting topics in the system (reuse when semantically equivalent): {topic_list}"
        )

    return [
        {"role": "system", "content": KEYWORD_TOPIC_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_stance_messages(
    transcript_text: str, topics: list[str]
) -> list[dict]:
    """Build the messages list for Pass 2 (stance classification).

    The topics list from Pass 1 is required input so the LLM classifies stances
    on exactly those topics.
    """
    topic_list = ", ".join(topics)
    user_content = (
        f"Classify each speaker's stance on these topics: {topic_list}"
        f"\n\nDebate transcript:\n\n{transcript_text}"
    )

    return [
        {"role": "system", "content": STANCE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
