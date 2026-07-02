"""Phase 2: Structure — speaker tagging + chapter detection."""
import json
import re
from collections import Counter
from pathlib import Path
from . import RAW_DIR, STRUCT_DIR
from .state import set_phase

# Parker-identifying regex patterns
PARKER_STRONG_PATTERNS = [
    r"only send a guest request", r"meet that set of criteria",
    r"we are (just )?looking for (some )?debates",
    r"let'?s go (on )?to the next person", r"listed on the screen",
    r"on the tik tok stream", r"joining up the live",
    r"if you could go back in time", r"kla harris or donald trump",
    r"who would you vote for", r"what'?s your birth year",
    r"and what month", r"how old are you", r"do you support donald trump",
    r"why (would|do) you support", r"why (would|do) you vote for",
    r"appreciate (it|you)", r"thank you (so much|for)",
    r"i have a few people to (thank|think)", r"let me let the",
    r"how'?s everybody doing",
]
PARKER_STRONG_RE = re.compile("|".join(PARKER_STRONG_PATTERNS), re.IGNORECASE)

PARKER_MODERATE_PATTERNS = [
    r"^for sure\.?$", r"^okay\.?\s*(for sure|um|so|and)?\.?$",
    r"^yo,? what'?s up", r"^hello\.?$", r"what do you (think|mean|say)",
    r"can (you|i) (explain|ask)",
    r"(studies|data|research) (show|say|indicate|suggest)",
]
PARKER_MODERATE_RE = re.compile("|".join(PARKER_MODERATE_PATTERNS), re.IGNORECASE)


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def merge_utterances(segments):
    """Merge raw transcript segments into logical utterances at >> markers."""
    utterances = []
    current_texts = []
    current_start = None
    current_end = None
    for seg in segments:
        text = seg["text"].strip()
        start = seg["start"]
        end = start + seg["duration"]
        if text.startswith(">>"):
            if current_texts:
                utterances.append({
                    "start": current_start, "end": current_end,
                    "text": " ".join(current_texts),
                })
            cleaned = text.lstrip(">").strip()
            current_texts = [cleaned] if cleaned else []
            current_start = start
            current_end = end
        elif ">>" in text:
            parts = text.split(">>")
            first = parts[0].strip()
            if first:
                current_texts.append(first)
                current_end = end
            if current_texts:
                utterances.append({
                    "start": current_start, "end": current_end,
                    "text": " ".join(current_texts),
                })
            rest = ">>".join(parts[1:]).strip()
            current_texts = [rest] if rest else []
            current_start = start
            current_end = end
        else:
            if current_start is None:
                current_start = start
            current_texts.append(text)
            current_end = end
    if current_texts:
        utterances.append({
            "start": current_start, "end": current_end,
            "text": " ".join(current_texts),
        })
    return utterances


def score_parker(text):
    """Score how likely an utterance is Parker saying it."""
    score = 0.0
    text_lower = text.lower().strip()
    if PARKER_STRONG_RE.search(text_lower):
        score += 3.0
    if PARKER_MODERATE_RE.search(text_lower):
        score += 1.5
    question_count = text.count("?")
    if question_count > 0:
        score += 0.3 * question_count
    policy_words = [
        "policy", "bipartisan", "legislation", "progressive", "conservative",
        "statistic", "percent", "billion", "according to", "studies show",
    ]
    for pw in policy_words:
        if pw in text_lower:
            score += 0.2
    if len(text_lower.split()) <= 3:
        score -= 0.5
    return score


def detect_guest_chapters(utterances):
    """Find guest conversation boundaries via intro phrases and large gaps."""
    chapters = []
    current_start = 0
    chapter_num = 0
    intro_re = re.compile(
        r"what'?s your birth year|how old are you|do you support (donald|trump)|"
        r"who did you vote for|welcome to the stream|what'?s your name",
        re.IGNORECASE,
    )
    for i, utt in enumerate(utterances):
        is_intro = intro_re.search(utt["text"])
        big_gap = i > 0 and (utt["start"] - max(
            utterances[j]["end"] for j in range(current_start, i) if j < len(utterances)
        ) if current_start < i else 0) > 60

        # Use simpler gap detection
        if i > 0:
            gap = utt["start"] - utterances[i-1]["end"]
        else:
            gap = 0

        if (is_intro or gap > 60) and i > 5:
            if current_start < i:
                chapters.append({
                    "chapter": chapter_num,
                    "start_idx": current_start,
                    "end_idx": i - 1,
                    "start_time": utterances[current_start]["start"],
                    "end_time": utterances[i-1]["end"],
                })
                chapter_num += 1
                current_start = i

    # Final chapter
    if current_start < len(utterances):
        chapters.append({
            "chapter": chapter_num,
            "start_idx": current_start,
            "end_idx": len(utterances) - 1,
            "start_time": utterances[current_start]["start"],
            "end_time": utterances[-1]["end"],
        })

    # Merge short chapters (<3 min)
    merged = []
    for ch in chapters:
        dur = ch["end_time"] - ch["start_time"]
        if merged and dur < 180:
            merged[-1]["end_idx"] = ch["end_idx"]
            merged[-1]["end_time"] = ch["end_time"]
        else:
            merged.append(dict(ch))
    for i, ch in enumerate(merged):
        ch["chapter"] = i
    return merged


def label_speakers(utterances, chapters):
    """Assign speaker labels via hybrid heuristic (regex + turn alternation)."""
    if not utterances:
        return utterances

    utt_to_chapter = {}
    for ch in chapters:
        for idx in range(ch["start_idx"], ch["end_idx"] + 1):
            utt_to_chapter[idx] = ch["chapter"]

    scores = [score_parker(u["text"]) for u in utterances]
    prev_speaker = "parker"

    for i, utt in enumerate(utterances):
        ch_num = utt_to_chapter.get(i, 0)
        guest_label = f"guest_{max(ch_num, 1)}"
        score = scores[i]

        # Alternation baseline
        if i == 0:
            toggle = "parker"
        elif prev_speaker == "parker":
            toggle = guest_label
        else:
            toggle = "parker"

        # Score overrides
        if score >= 2.0:
            utt["speaker"] = "parker"
            utt["speaker_confidence"] = "high"
        elif score >= 1.0 and toggle != "parker":
            utt["speaker"] = "parker"
            utt["speaker_confidence"] = "medium"
        else:
            utt["speaker"] = toggle
            utt["speaker_confidence"] = "low"

        prev_speaker = utt["speaker"]

    return utterances


def run(conn, video_id):
    """Execute structure phase. Returns structured dict path or raises."""
    set_phase(conn, video_id, "structure", "running")

    raw_path = RAW_DIR / f"{video_id}.json"
    if not raw_path.exists():
        msg = f"Raw transcript not found: {raw_path}"
        set_phase(conn, video_id, "structure", "failed", msg)
        raise FileNotFoundError(msg)

    with open(raw_path) as f:
        raw = json.load(f)

    print(f"Structuring: {raw.get('title', video_id)}")
    print(f"  Raw segments: {raw['segment_count']}")

    utterances = merge_utterances(raw["segments"])
    print(f"  Merged into {len(utterances)} utterances")

    chapters = detect_guest_chapters(utterances)
    print(f"  Detected {len(chapters)} chapters")

    utterances = label_speakers(utterances, chapters)

    speakers = sorted(set(u["speaker"] for u in utterances))
    parker_count = sum(1 for u in utterances if u["speaker"] == "parker")
    guest_count = len([s for s in speakers if s != "parker"])
    conf = Counter(u.get("speaker_confidence", "?") for u in utterances)
    print(f"  Speakers: parker ({parker_count}) + {guest_count} guests "
          f"({len(utterances) - parker_count} utterances)")
    print(f"  Confidence: {', '.join(f'{k}={v}' for k, v in sorted(conf.items()))}")

    # Print chapter summaries
    for ch in chapters:
        dur = ch["end_time"] - ch["start_time"]
        ch_speakers = set()
        for idx in range(ch["start_idx"], ch["end_idx"] + 1):
            if idx < len(utterances) and utterances[idx]["speaker"] != "parker":
                ch_speakers.add(utterances[idx]["speaker"])
        spk_str = ", ".join(sorted(ch_speakers)) if ch_speakers else "intro"
        print(f"    Ch{ch['chapter']}: {fmt_ts(ch['start_time'])} - "
              f"{fmt_ts(ch['end_time'])} ({dur/60:.0f}m) [{spk_str}]")

    structured = {
        "video_id": raw["video_id"],
        "url": raw["url"],
        "title": raw["title"],
        "author": raw.get("author", ""),
        "is_auto_generated": raw.get("is_auto_generated", False),
        "total_duration_sec": raw["total_duration_sec"],
        "utterance_count": len(utterances),
        "chapter_count": len(chapters),
        "speakers": speakers,
        "chapters": chapters,
        "utterances": utterances,
    }

    Path(STRUCT_DIR).mkdir(parents=True, exist_ok=True)
    out_path = STRUCT_DIR / f"{video_id}.structured.json"
    with open(out_path, "w") as f:
        json.dump(structured, f, indent=2, ensure_ascii=False)

    # Update video metadata in DB
    conn.execute(
        """UPDATE videos SET
           utterance_count=?, chapter_count=?, speakers=?
           WHERE video_id=?""",
        (len(utterances), len(chapters), json.dumps(speakers), video_id),
    )
    conn.commit()

    set_phase(conn, video_id, "structure", "done")
    print(f"  Saved to {out_path}")
    return str(out_path)
