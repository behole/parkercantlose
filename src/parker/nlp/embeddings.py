"""Topic embedding generation and cross-debate similarity matching."""

import json
import logging

import numpy as np

from parker.models import Topic, TopicMatch

logger = logging.getLogger(__name__)

# Module-level singleton for model caching (avoids repeated 5-30s load times)
_model = None


def _get_model(model_name: str = "all-MiniLM-L6-v2"):
    """Lazy-load sentence transformer model. Cached after first call."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
    return _model


def generate_embedding(text: str, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """Generate embedding vector for a text string. Returns list of floats."""
    model = _get_model(model_name)
    embedding = model.encode([text])[0]
    return embedding.tolist()


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a = np.array(vec_a)
    b = np.array(vec_b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def embed_topic(topic: Topic, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """Generate and return embedding for a topic. Uses name + description for richer representation."""
    text = topic.name
    if topic.description:
        text = f"{topic.name}: {topic.description}"
    return generate_embedding(text, model_name)


def store_topic_embedding(
    session, topic: Topic, model_name: str = "all-MiniLM-L6-v2"
) -> Topic:
    """Generate embedding for a topic and store it in topic.embedding_json."""
    embedding = embed_topic(topic, model_name)
    topic.embedding_json = json.dumps(embedding)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def get_topic_embedding(topic: Topic) -> list[float] | None:
    """Parse stored embedding from topic.embedding_json. Returns None if not embedded."""
    if topic.embedding_json is None:
        return None
    return json.loads(topic.embedding_json)


def find_matching_topics(
    new_topics: list[Topic],
    existing_topics: list[Topic],
    threshold: float = 0.7,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[tuple[Topic, Topic, float]]:
    """Find potential topic matches above similarity threshold.

    Compares new_topics against existing_topics using embedding cosine similarity.
    Returns list of (new_topic, existing_topic, similarity_score) tuples.
    Skips topics from the same debate (same-debate topics are already distinct).
    """
    if not new_topics or not existing_topics:
        return []

    model = _get_model(model_name)

    # Build text representations
    new_texts = [
        f"{t.name}: {t.description}" if t.description else t.name
        for t in new_topics
    ]
    existing_texts = [
        f"{t.name}: {t.description}" if t.description else t.name
        for t in existing_topics
    ]

    # Batch encode for efficiency
    new_emb = model.encode(new_texts)
    existing_emb = model.encode(existing_texts)

    # Compute pairwise cosine similarity matrix
    # Normalize vectors
    new_norms = np.linalg.norm(new_emb, axis=1, keepdims=True)
    existing_norms = np.linalg.norm(existing_emb, axis=1, keepdims=True)
    # Avoid division by zero
    new_norms = np.where(new_norms == 0, 1, new_norms)
    existing_norms = np.where(existing_norms == 0, 1, existing_norms)

    similarities = np.dot(new_emb / new_norms, (existing_emb / existing_norms).T)

    matches = []
    for i, new_topic in enumerate(new_topics):
        for j, existing_topic in enumerate(existing_topics):
            # Skip same-debate topics
            if new_topic.debate_id == existing_topic.debate_id:
                continue
            sim = float(similarities[i][j])
            if sim >= threshold:
                matches.append((new_topic, existing_topic, sim))

    # Sort by similarity descending
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches


def create_topic_matches(
    session,
    new_topics: list[Topic],
    existing_topics: list[Topic],
    threshold: float = 0.7,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[TopicMatch]:
    """Find matching topics and create TopicMatch rows with status='suggested'.

    Also generates and stores embeddings for new_topics that don't have them yet.
    """
    # Ensure new topics have embeddings stored
    for topic in new_topics:
        if topic.embedding_json is None:
            store_topic_embedding(session, topic, model_name)

    # Ensure existing topics have embeddings stored
    for topic in existing_topics:
        if topic.embedding_json is None:
            store_topic_embedding(session, topic, model_name)

    matches = find_matching_topics(new_topics, existing_topics, threshold, model_name)

    created = []
    for new_topic, existing_topic, similarity in matches:
        # Avoid duplicate matches (check both directions)
        from sqlmodel import select

        existing_match = session.exec(
            select(TopicMatch).where(
                (
                    (TopicMatch.topic_a_id == new_topic.id)
                    & (TopicMatch.topic_b_id == existing_topic.id)
                )
                | (
                    (TopicMatch.topic_a_id == existing_topic.id)
                    & (TopicMatch.topic_b_id == new_topic.id)
                )
            )
        ).first()
        if existing_match:
            continue

        match = TopicMatch(
            topic_a_id=new_topic.id,
            topic_b_id=existing_topic.id,
            similarity=similarity,
            status="suggested",
        )
        session.add(match)
        created.append(match)

    if created:
        session.commit()
        for m in created:
            session.refresh(m)

    logger.info(
        "Created %d topic match suggestions (threshold=%.2f)", len(created), threshold
    )
    return created
