"""Domain-specific stopword filtering for debate transcripts."""

DEBATE_STOPWORDS: set[str] = {
    # Common debate filler
    "well", "look", "so", "right", "okay", "yeah", "yes", "no",
    "um", "uh", "like", "actually", "basically", "literally",
    "honestly", "clearly", "obviously", "absolutely",
    # Common debate transitions
    "let me", "hold on", "wait a minute", "the point is",
    "what im saying is", "what youre saying is",
    "let me tell you", "heres the thing",
    # Host/caller meta-language
    "thanks for calling", "next caller", "go ahead",
    "youre on the air", "welcome to the show",
    # Generic filler phrases
    "you know", "i mean", "kind of", "sort of",
    "at the end of the day", "the bottom line",
    "the reality is", "the truth is",
}


def filter_stopwords(phrases: list[str]) -> list[str]:
    """Remove domain-specific debate stopwords from a phrase list."""
    return [p for p in phrases if p.lower().strip() not in DEBATE_STOPWORDS]


def is_stopword(phrase: str) -> bool:
    """Check if a single phrase is a debate stopword."""
    return phrase.lower().strip() in DEBATE_STOPWORDS
