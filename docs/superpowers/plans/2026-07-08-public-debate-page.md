# Public Debate Page Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the public debate detail page with natural-language slugs, synced video+transcript playback, and a clean gradient-free layout.

**Architecture:** Add a `slug` column to the `Debate` model with auto-generation from the title. New canonical route `/debate/{slug}` with the old `/debate/{youtube_id}` route becoming a 301 redirect. Rewrite `debate_detail.html` to use the review page's two-panel layout (sticky video left, scrollable synced transcript right) via a new `public-debate.js`. Drop the gradient banner and old transcript-list styles.

**Tech Stack:** Python 3.11, FastAPI, Jinja2, SQLModel/SQLAlchemy, YouTube IFrame API (CDN), no new Python deps.

---

### Task 1: Add `slug` field to `Debate` model

**Files:**
- Modify: `src/parker/models.py:49-65`

- [ ] **Step 1: Add `slug` field to the `Debate` class**

In `src/parker/models.py`, find the `Debate` class (line 49). Add a `slug` field after the `url` field (line 53):

```python
class Debate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    youtube_id: str = Field(unique=True, index=True)
    title: str
    url: str
    slug: Optional[str] = Field(default=None, index=True)
    duration_seconds: Optional[float] = None
    upload_date: Optional[str] = None
    status: VideoStatus = Field(default=VideoStatus.PENDING)
    error_message: Optional[str] = None
    audio_path: Optional[str] = None
    raw_transcript_path: Optional[str] = None
    schema_version: int = Field(default=1)
    review_status: ReviewStatus = Field(default=ReviewStatus.UNREVIEWED)
    guest_id: Optional[int] = Field(default=None, foreign_key="guest.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    utterances: List[Utterance] = Relationship(back_populates="debate")
```

- [ ] **Step 2: Verify model imports cleanly**

```bash
.venv/bin/python -c "from parker.models import Debate; print(Debate.model_fields.keys())"
```
Expected: includes `'slug'` in the output

- [ ] **Step 3: Commit**

```bash
git add src/parker/models.py
git commit -m "feat: add slug field to Debate model"
```

---

### Task 2: Write failing tests for slug generation

**Files:**
- Modify: `tests/test_crud.py` (append at end)

- [ ] **Step 1: Add slug tests to the end of `tests/test_crud.py`**

```python
from parker.crud import (
    generate_slug,
    get_debate_by_slug,
    assign_slug,
)


def test_generate_slug_basic(settings):
    assert generate_slug("Parker vs. John on Immigration Policy") == "parker-john-immigration-policy"


def test_generate_slug_strips_stopwords(settings):
    assert generate_slug("Parker and the Caller on the Economy") == "parker-caller-economy"


def test_generate_slug_truncates_long_titles(settings):
    long_title = "Parker Debates a Very Long Windy Caller About Multiple Topics at Great Length"
    slug = generate_slug(long_title)
    assert len(slug) <= 50
    assert not slug.endswith("-")


def test_generate_slug_strips_punctuation(settings):
    assert generate_slug("Parker vs. John: Immigration!!") == "parker-john-immigration"


def test_generate_slug_empty_title(settings):
    assert generate_slug("") == "debate"
    assert generate_slug("   ") == "debate"


def test_get_debate_by_slug_not_found(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        found = get_debate_by_slug(session, "nonexistent-slug")
    assert found is None


def test_assign_slug_no_collision(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d = create_debate(session, "abc123", "Parker vs John on Immigration", "https://youtube.com/watch?v=abc123")
        slug = assign_slug(session, d.id)
    assert slug == "parker-john-immigration"

    with get_session(engine) as session:
        found = get_debate_by_slug(session, "parker-john-immigration")
    assert found is not None
    assert found.id == d.id


def test_assign_slug_collision_appends_youtube_id(settings):
    engine = get_engine(settings.db_path)
    init_db(engine)
    with get_session(engine) as session:
        d1 = create_debate(session, "abc123", "Parker vs John on Immigration", "https://youtube.com/watch?v=abc123")
        d2 = create_debate(session, "def456", "Parker vs John on Immigration", "https://youtube.com/watch?v=def456")
        slug1 = assign_slug(session, d1.id)
        slug2 = assign_slug(session, d2.id)
    assert slug1 == "parker-john-immigration"
    assert slug2 != slug1
    assert slug2.startswith("parker-john-immigration-")
    assert "def456"[-6:] in slug2 or "def456" in slug2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_crud.py -k slug -v
```
Expected: All FAIL with `ImportError: cannot import name 'generate_slug'`

---

### Task 3: Implement slug generation and lookup in `crud.py`

**Files:**
- Modify: `src/parker/crud.py` (add after `get_debate_by_youtube_id`, around line 43)

- [ ] **Step 1: Add slug functions after `get_debate_by_youtube_id`**

Insert this block right after the `get_debate_by_youtube_id` function (after line 43):

```python
import re

_SLUG_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "on", "in", "at", "to",
    "vs", "vs.", "about", "of", "for", "with", "is", "are",
})
_SLUG_MAX_LEN = 50


def generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a debate title.

    Lowercases, strips stopwords/punctuation, hyphenates, truncates to ~50 chars.
    Falls back to 'debate' for empty input.
    """
    if not title or not title.strip():
        return "debate"
    words = re.findall(r"[a-z0-9]+", title.lower())
    kept = [w for w in words if w not in _SLUG_STOPWORDS]
    if not kept:
        return "debate"
    slug = "-".join(kept)
    if len(slug) <= _SLUG_MAX_LEN:
        return slug
    truncated = slug[:_SLUG_MAX_LEN]
    if "-" in truncated:
        truncated = truncated[: truncated.rfind("-")]
    return truncated or "debate"


def get_debate_by_slug(session: Session, slug: str) -> Debate | None:
    """Look up a debate by its slug."""
    statement = select(Debate).where(Debate.slug == slug)
    return session.exec(statement).first()


def assign_slug(session: Session, debate_id: int) -> str:
    """Generate and assign a unique slug to a debate.

    On collision, appends the YouTube ID suffix to disambiguate.
    Returns the assigned slug.
    """
    debate = session.get(Debate, debate_id)
    if debate is None:
        raise ValueError(f"Debate {debate_id} not found")
    base_slug = generate_slug(debate.title)
    slug = base_slug
    while True:
        existing = session.exec(
            select(Debate).where(Debate.slug == slug, Debate.id != debate_id)
        ).first()
        if existing is None:
            break
        slug = f"{base_slug}-{debate.youtube_id}"
        # Final safety: if even that collides, append a counter
        counter = 2
        candidate = slug
        while session.exec(
            select(Debate).where(Debate.slug == candidate, Debate.id != debate_id)
        ).first() is not None:
            candidate = f"{slug}-{counter}"
            counter += 1
        slug = candidate
        break
    debate.slug = slug
    debate.updated_at = datetime.utcnow()
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return slug
```

Note: `re` is a stdlib module — add the `import re` at the top of the new block (it will be a module-level import; if `re` is already imported elsewhere in crud.py it's fine to leave it, but it isn't, so place it just above the slug code or at the file top).

- [ ] **Step 2: Run the slug tests**

```bash
.venv/bin/python -m pytest tests/test_crud.py -k slug -v
```
Expected: All slug tests PASS

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: All tests pass (previous + new slug tests)

- [ ] **Step 4: Commit**

```bash
git add src/parker/crud.py tests/test_crud.py
git commit -m "feat: add slug generation, lookup, and assignment to crud layer"
```

---

### Task 4: Auto-assign slug on debate creation

**Files:**
- Modify: `src/parker/crud.py:19-37` (`create_debate`)

- [ ] **Step 1: Update `create_debate` to auto-assign a slug**

Replace the `create_debate` function (lines 19-37) with:

```python
def create_debate(
    session: Session,
    youtube_id: str,
    title: str,
    url: str,
    duration_seconds: float | None = None,
    upload_date: str | None = None,
) -> Debate:
    debate = Debate(
        youtube_id=youtube_id,
        title=title,
        url=url,
        duration_seconds=duration_seconds,
        upload_date=upload_date,
    )
    session.add(debate)
    session.commit()
    session.refresh(debate)
    debate.slug = assign_slug(session, debate.id)
    return debate
```

- [ ] **Step 2: Run the slug tests + create_debate tests**

```bash
.venv/bin/python -m pytest tests/test_crud.py -v
```
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/parker/crud.py
git commit -m "feat: auto-assign slug on debate creation"
```

---

### Task 5: Add slug backfill CLI command

**Files:**
- Modify: `src/parker/cli.py` (add after the `cleanup` command, around line 129)

- [ ] **Step 1: Add `backfill-slugs` command after `cleanup`**

Insert this after the `cleanup` function (after line 128):

```python
@app.command(name="backfill-slugs")
def backfill_slugs() -> None:
    """Generate slugs for existing debates that don't have one yet."""
    from parker.crud import assign_slug, get_all_debates
    from parker.db import get_session

    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)

    with get_session(engine) as session:
        debates = get_all_debates(session)
        missing = [d for d in debates if not d.slug]
        if not missing:
            typer.echo("All debates already have slugs.")
            return
        typer.echo(f"Backfilling slugs for {len(missing)} debate(s)...")
        for d in missing:
            slug = assign_slug(session, d.id)
            typer.echo(f"  {d.youtube_id}: {d.title[:40]:<40} -> {slug}")
```

- [ ] **Step 2: Verify the command is registered**

```bash
.venv/bin/python -m parker.cli backfill-slugs --help
```
Expected: Shows help text for the command

- [ ] **Step 3: Commit**

```bash
git add src/parker/cli.py
git commit -m "feat: add backfill-slugs CLI command"
```

---

### Task 6: Update routes — slug canonical, youtube_id redirect

**Files:**
- Modify: `src/parker/web/public_routes.py:52-87`

- [ ] **Step 1: Update the `debate_detail` route to look up by slug OR youtube_id, and add a redirect route**

Replace the existing `debate_detail` function (lines 52-87) with two functions:

```python
from fastapi import HTTPException
from starlette.responses import RedirectResponse


@router.get("/debate/{identifier}", response_class=HTMLResponse)
async def debate_detail(request: Request, identifier: str):
    templates = _get_templates(request)
    engine = _get_engine(request)
    with get_session(engine) as session:
        # Try slug first, then youtube_id (backward compat)
        debate = crud.get_debate_by_slug(session, identifier)
        if debate is None:
            debate = crud.get_debate_by_youtube_id(session, identifier)
        if debate is None:
            raise HTTPException(status_code=404, detail=f"Debate not found: {identifier}")
        # If we matched by youtube_id but debate has a slug, redirect to canonical slug URL
        if debate.slug and debate.slug != identifier:
            return RedirectResponse(url=f"/debate/{debate.slug}", status_code=301)
        topics = crud.get_topics_for_debate(session, debate.id)
        all_stances = crud.get_stances_for_debate(session, debate.id)
        keywords = crud.get_keywords_for_debate(session, debate.id)
        utterances = crud.get_utterances_for_debate(session, debate.id)

        stances_by_topic: dict[int, list] = {}
        for stance in all_stances:
            stances_by_topic.setdefault(stance.topic_id, []).append(stance)

        parker_keywords = [k for k in keywords if k.speaker == "parker"][:10]
        caller_keywords = [k for k in keywords if k.speaker == "caller"][:10]

    return templates.template_response(
        "debate_detail.html",
        {
            "request": request,
            "debate": debate,
            "youtube_id": debate.youtube_id,
            "topics": topics,
            "stances_by_topic": stances_by_topic,
            "parker_keywords": parker_keywords,
            "caller_keywords": caller_keywords,
            "keywords": keywords,
            "utterances": utterances,
        },
    )
```

Note: The `from fastapi import HTTPException` and `from starlette.responses import RedirectResponse` imports should go at the top of the file with the other imports (lines 1-3). Move them there rather than inside the function.

- [ ] **Step 2: Verify route imports**

```bash
.venv/bin/python -c "from parker.web.public_routes import router; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/parker/web/public_routes.py
git commit -m "feat: slug-canonical debate route with youtube_id 301 redirect"
```

---

### Task 7: Update templates to link via slug

**Files:**
- Modify: `src/parker/web/templates/partials/debate_cards.html:5`
- Modify: `src/parker/web/templates/dashboard.html:49`
- Modify: `src/parker/web/templates/topic_drilldown.html:21`
- Modify: `src/parker/web/templates/search_results.html:20`

- [ ] **Step 1: Update `debate_cards.html`**

Change line 5 from:
```html
        <a href="/debate/{{ debate.youtube_id }}">{{ debate.title }}</a>
```
to:
```html
        <a href="/debate/{{ debate.slug or debate.youtube_id }}">{{ debate.title }}</a>
```

- [ ] **Step 2: Update `dashboard.html`**

Change line 49 from:
```html
      &mdash; <a href="/debate/{{ act.youtube_id }}">{{ act.title }}</a>
```
to:
```html
      &mdash; <a href="/debate/{{ act.slug or act.youtube_id }}">{{ act.title }}</a>
```

Note: this requires the `get_recent_activity` function in `analytics.py` to include `slug` in its dict output. Check and update it in Task 7b.

- [ ] **Step 3: Update `topic_drilldown.html`**

The `get_topic_stances_across_debates` function in `crud.py` returns dicts with `debate_youtube_id` but not `slug`. For the drilldown, we'll keep using youtube_id (the redirect will handle canonicalization). Leave this template as-is — the 301 redirect covers it.

- [ ] **Step 4: Update `search_results.html`**

Same as topic_drilldown — the search results dict has `youtube_id` but not `slug`. Leave as-is; the 301 redirect handles it.

- [ ] **Step 5: Commit**

```bash
git add src/parker/web/templates/partials/debate_cards.html src/parker/web/templates/dashboard.html
git commit -m "feat: link debate cards and dashboard activity via slug"
```

---

### Task 7b: Add `slug` to recent activity data

**Files:**
- Modify: `src/parker/analytics.py` (the `get_recent_activity` function)

- [ ] **Step 1: Find `get_recent_activity` and add `slug` to the dict**

In `src/parker/analytics.py`, find `get_recent_activity`. It returns a list of dicts with keys `title`, `youtube_id`, `status`, `review_status`, `updated_at`. Add `"slug": d.slug` to the dict:

```python
def get_recent_activity(session: Session, limit: int = 8) -> list[dict]:
    debates = session.exec(
        select(Debate)
        .order_by(Debate.updated_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "title": d.title,
            "youtube_id": d.youtube_id,
            "slug": d.slug,
            "status": d.status.value,
            "review_status": d.review_status.value,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
        }
        for d in debates
    ]
```

- [ ] **Step 2: Verify analytics imports**

```bash
.venv/bin/python -c "from parker.analytics import get_recent_activity; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/parker/analytics.py
git commit -m "feat: include slug in recent activity data"
```

---

### Task 8: Create `public-debate.js` — synced transcript logic

**Files:**
- Create: `src/parker/web/static/public-debate.js`

- [ ] **Step 1: Write the sync JS file**

```javascript
/* YouTube IFrame API + Transcript Sync (public read-only page) */

let player = null;
let syncInterval = null;
let activeSegmentId = null;

function onYouTubeIframeAPIReady() {
  player = new YT.Player('player', {
    videoId: window.YOUTUBE_VIDEO_ID,
    playerVars: {
      autoplay: 0,
      modestbranding: 1,
      rel: 0,
    },
    events: {
      onReady: onPlayerReady,
      onStateChange: onPlayerStateChange,
    },
  });
}

function onPlayerReady() {
  syncInterval = setInterval(syncTranscript, 250);
}

function onPlayerStateChange(event) {
  if (event.data === 1 && !syncInterval) {
    syncInterval = setInterval(syncTranscript, 250);
  }
}

function syncTranscript() {
  if (!player || typeof player.getCurrentTime !== 'function') return;

  const currentTime = player.getCurrentTime();
  const segments = document.querySelectorAll('.segment[data-start]');
  let found = null;

  segments.forEach(seg => {
    const start = parseFloat(seg.dataset.start);
    const end = parseFloat(seg.dataset.end);
    if (currentTime >= start && currentTime < end) {
      found = seg;
    }
  });

  if (found && found.id !== activeSegmentId) {
    if (activeSegmentId) {
      const prev = document.getElementById(activeSegmentId);
      if (prev) prev.classList.remove('segment--active');
    }
    found.classList.add('segment--active');
    activeSegmentId = found.id;

    const toggle = document.getElementById('auto-scroll-toggle');
    if (toggle && toggle.checked) {
      found.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

function seekTo(seconds) {
  if (player && typeof player.seekTo === 'function') {
    player.seekTo(seconds, true);
    player.playVideo();
  }
}

function filterTranscript(query) {
  var entries = document.querySelectorAll('.segment');
  var q = query.toLowerCase().trim();
  entries.forEach(function(el) {
    if (!q || el.dataset.text.includes(q)) {
      el.style.display = '';
    } else {
      el.style.display = 'none';
    }
  });
}
```

- [ ] **Step 2: Verify the file exists and is served**

```bash
ls -la src/parker/web/static/public-debate.js
```
Expected: file exists

- [ ] **Step 3: Commit**

```bash
git add src/parker/web/static/public-debate.js
git commit -m "feat: add public-debate.js for synced transcript playback"
```

---

### Task 9: Rewrite `debate_detail.html` — two-panel layout, no gradient

**Files:**
- Modify: `src/parker/web/templates/debate_detail.html` (full rewrite)

- [ ] **Step 1: Rewrite the template**

```html
{% extends "public_base.html" %}
{% block title %}{{ debate.title }} - Parker Debate Dashboard{% endblock %}
{% block og_title %}{{ debate.title }}{% endblock %}
{% block og_description %}Explore topics, stances, and key quotes from this debate.{% endblock %}

{% block content %}

<nav aria-label="breadcrumb">
  <ul>
    <li><a href="/">Home</a></li>
    <li>{{ debate.title }}</li>
  </ul>
</nav>

<h1>{{ debate.title }}</h1>
<div class="debate-meta">
  {% if debate.upload_date %}
  <span>{{ debate.upload_date[:4] }}-{{ debate.upload_date[4:6] }}-{{ debate.upload_date[6:8] }}</span>
  {% endif %}
  {% if debate.duration_seconds %}
  <span>{{ debate.duration_seconds // 60 }} min {{ debate.duration_seconds % 60 }}s</span>
  {% endif %}
</div>

<div class="review-layout">
  <div class="video-panel">
    <div id="player-wrap">
      <div id="player"></div>
    </div>
    <div class="video-controls">
      <label>
        <input type="checkbox" id="auto-scroll-toggle" checked>
        Auto-scroll transcript
      </label>
    </div>
  </div>

  <div class="transcript-panel" id="transcript-panel">
    {% if utterances %}
    <div class="transcript-search">
      <input type="text" id="transcript-search-input" placeholder="Search transcript..." oninput="filterTranscript(this.value)">
    </div>
    {% for u in utterances %}
    <div class="segment"
         id="segment-{{ u.id }}"
         data-start="{{ u.start_time }}"
         data-end="{{ u.end_time }}"
         data-text="{{ u.text | lower }}">
      <span class="segment-time" onclick="seekTo({{ u.start_time }})">
        {{ '%d:%02d' % (u.start_time // 60, u.start_time % 60) }}
      </span>
      <span class="speaker-badge speaker-{{ u.speaker }}">{{ u.speaker }}</span>
      <span class="segment-text">{{ u.text }}</span>
    </div>
    {% endfor %}
    {% else %}
    <p>No transcript available for this debate.</p>
    {% endif %}
  </div>
</div>

{% if topics %}
<section>
  <h2>Topics &amp; Stances</h2>
  {% for topic in topics %}
  <article style="margin-bottom: 1.5rem;">
    <h3>{{ topic.name }}</h3>
    {% if topic.description %}
    <p style="color: var(--pico-muted-color); margin-bottom: 0.5rem;">{{ topic.description }}</p>
    {% endif %}

    {% set topic_stances = stances_by_topic.get(topic.id, []) %}
    {% set parker_s = topic_stances | selectattr('speaker', 'equalto', 'parker') | list %}
    {% set caller_s = topic_stances | selectattr('speaker', 'equalto', 'caller') | list %}

    <div class="stance-comparison">
      <div class="stance-card">
        <h4 style="margin: 0 0 0.5rem 0; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;">
          <span class="speaker-badge speaker-parker" style="cursor: default;">PARKER</span>
        </h4>
        {% for stance in parker_s %}
        <span class="stance-label {{ stance.label | lower }}">{{ stance.label }}</span>
        <div class="confidence-bar-wrap">
          <div class="confidence-bar {{ stance.label | lower }}" style="width: {{ "%.0f" | format(stance.confidence * 100) }}%"></div>
        </div>
        <span style="font-size: 0.8rem; color: var(--pico-muted-color);">{{ "%.0f" | format(stance.confidence * 100) }}% confidence</span>
        {% if stance.evidence %}
        <p class="stance-evidence">{{ stance.evidence }}</p>
        {% endif %}
        {% else %}
        <p style="color: var(--pico-muted-color); font-size: 0.9rem;">No stance recorded</p>
        {% endfor %}
      </div>

      <div class="stance-card">
        <h4 style="margin: 0 0 0.5rem 0; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;">
          <span class="speaker-badge speaker-caller" style="cursor: default;">CALLER</span>
        </h4>
        {% for stance in caller_s %}
        <span class="stance-label {{ stance.label | lower }}">{{ stance.label }}</span>
        <div class="confidence-bar-wrap">
          <div class="confidence-bar {{ stance.label | lower }}" style="width: {{ "%.0f" | format(stance.confidence * 100) }}%"></div>
        </div>
        <span style="font-size: 0.8rem; color: var(--pico-muted-color);">{{ "%.0f" | format(stance.confidence * 100) }}% confidence</span>
        {% if stance.evidence %}
        <p class="stance-evidence">{{ stance.evidence }}</p>
        {% endif %}
        {% else %}
        <p style="color: var(--pico-muted-color); font-size: 0.9rem;">No stance recorded</p>
        {% endfor %}
      </div>
    </div>
  </article>
  {% endfor %}
</section>
{% endif %}

{% if keywords %}
<section class="keywords-section">
  <h2>Key Phrases</h2>
  <div class="keywords-grid">
    <div>
      <h4 style="margin-bottom: 0.5rem;">Parker</h4>
      {% if parker_keywords %}
      <ul class="keyword-list">
        {% for kw in parker_keywords %}
        <li><span>{{ kw.phrase }}</span> <span class="keyword-count">{{ kw.count }}</span></li>
        {% endfor %}
      </ul>
      {% else %}
      <p style="color: var(--pico-muted-color);">No keywords</p>
      {% endif %}
    </div>
    <div>
      <h4 style="margin-bottom: 0.5rem;">Caller</h4>
      {% if caller_keywords %}
      <ul class="keyword-list">
        {% for kw in caller_keywords %}
        <li><span>{{ kw.phrase }}</span> <span class="keyword-count">{{ kw.count }}</span></li>
        {% endfor %}
      </ul>
      {% else %}
      <p style="color: var(--pico-muted-color);">No keywords</p>
      {% endif %}
    </div>
  </div>
</section>
{% endif %}

{% endblock %}

{% block scripts %}
<script>
  window.YOUTUBE_VIDEO_ID = "{{ youtube_id }}";
</script>
<script src="https://www.youtube.com/iframe_api"></script>
<script src="/static/public-debate.js"></script>
{% endblock %}
```

- [ ] **Step 2: Verify template parses (start server briefly)**

```bash
.venv/bin/python -c "from parker.web import create_app; app = create_app(); print('OK')"
```
Expected: `OK` (confirms templates compile and routes load)

- [ ] **Step 3: Commit**

```bash
git add src/parker/web/templates/debate_detail.html
git commit -m "feat: rewrite debate detail with two-panel synced layout, no gradient"
```

---

### Task 10: Clean up CSS — remove gradient and old transcript styles

**Files:**
- Modify: `src/parker/web/static/style.css`

- [ ] **Step 1: Remove the `.debate-header` gradient block and `.debate-embed` rules**

Find the `/* Debate Detail */` section (around line 543). Remove these rules:
- `.debate-header { ... }` (the gradient background)
- `.debate-header h1 { ... }` (the white color override)
- `.debate-embed { ... }`
- `.debate-embed iframe { ... }`

Keep `.debate-meta` (it's still used for the date/duration row).

Replace the block (lines ~543-583) with just:

```css
/* Debate Detail */
.debate-meta {
  display: flex;
  gap: 1.5rem;
  color: var(--pico-muted-color);
  font-size: 0.9rem;
  margin-bottom: 1.5rem;
}
```

- [ ] **Step 2: Remove old public transcript styles**

Find the `.transcript-section`, `.public-transcript`, `.transcript-entry`, `.transcript-entry:hover`, `.transcript-entry:nth-child(odd)`, `.transcript-time`, `.transcript-text` rules (around lines 682-735). Remove all of them — the public page now uses `.segment` / `.segment--active` styles which already exist.

Also remove `.public-transcript` from the shared `box-shadow` rule near line 104 (just remove `.public-transcript,` from that comma list).

- [ ] **Step 3: Add transcript-search input styling inside transcript-panel**

Near where the transcript-panel rules are, add:

```css
.transcript-search {
  margin-bottom: 0.75rem;
  position: sticky;
  top: 0;
  background: var(--pico-card-background-color, #fff);
  padding: 0.5rem 0;
  z-index: 2;
}

.transcript-search input {
  width: 100%;
  margin: 0;
}
```

- [ ] **Step 4: Verify CSS is valid (no syntax errors)**

```bash
.venv/bin/python -c "
from pathlib import Path
css = Path('src/parker/web/static/style.css').read_text()
# Basic brace balance check
assert css.count('{') == css.count('}'), 'Unbalanced braces'
print('CSS OK')
"
```
Expected: `CSS OK`

- [ ] **Step 5: Commit**

```bash
git add src/parker/web/static/style.css
git commit -m "style: remove gradient banner and old transcript-list CSS"
```

---

### Task 11: Run full test suite and lint

- [ ] **Step 1: Run all tests**

```bash
.venv/bin/python -m pytest tests/ -q
```
Expected: All tests pass (77 + new slug tests)

- [ ] **Step 2: Run linter**

```bash
.venv/bin/ruff check src/ tests/
```
Expected: All checks passed

- [ ] **Step 3: Run format check**

```bash
.venv/bin/ruff format --check src/ tests/
```
Expected: All checks passed (if not, run `ruff format src/ tests/` to fix)

- [ ] **Step 4: Fix any lint/format issues if found**

```bash
.venv/bin/ruff format src/ tests/
.venv/bin/ruff check --fix src/ tests/
```

---

### Task 12: Manual verification — start server and check pages

- [ ] **Step 1: Start the server**

```bash
.venv/bin/python -m parker.cli serve
```

- [ ] **Step 2: Visit and verify these pages**

- `http://127.0.0.1:8000/` — Dashboard loads, recent activity links use slug
- `http://127.0.0.1:8000/debates` — Debate list loads, card links use slug
- Click a debate → loads at `/debate/{slug}` — page renders with:
  - Clean title/meta (no gradient banner)
  - Two-panel layout: video left (sticky), transcript right (scrollable)
  - Play the video → transcript highlights active segment, auto-scrolls
  - Click a timestamp → video seeks to that time and plays
  - Type in search box → transcript filters by text
  - Topics & Stances section below
  - Key Phrases section below
- `http://127.0.0.1:8000/debate/{old_youtube_id}` → 301 redirects to `/debate/{slug}`

- [ ] **Step 3: Stop the server** (Ctrl+C)

---

### Task 13: Final commit and verification

- [ ] **Step 1: Check git status**

```bash
git status
```
Expected: clean working tree (all committed)

- [ ] **Step 2: Final lint + test run**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/python -m pytest tests/ -q
```
Expected: lint clean, all tests pass

---

## Summary of Changes

| Area | Change |
|------|--------|
| **Slugs** | New `slug` column on Debate, auto-generated on creation, backfill CLI command |
| **Routing** | `/debate/{slug}` canonical, `/debate/{youtube_id}` 301-redirects |
| **Layout** | Two-panel video+transcript with IFrame API sync, auto-scroll, click-to-seek |
| **Visual** | Removed gradient banner, clean title/meta, reuses review page's segment styling |
| **JS** | New `public-debate.js` (sync + seek + search-filter), `review.js` unchanged |
| **Templates** | `debate_detail.html` rewritten; dashboard/cards link via slug |
| **Backward compat** | Old YouTube-ID links still work (301 redirect) |
