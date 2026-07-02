#!/usr/bin/env python3
"""Phase 2 v3: Structure - Hybrid speaker tagging."""

import argparse, json, re, sys
from pathlib import Path

PARKER_STRONG = [
    r"only send a guest request",
    r"meet that set of criteria",
    r"we are (just )?looking for (some )?debates",
    r"let'?s go (on )?to the next person",
    r"listed on the screen",
    r"on the tik tok stream",
    r"joining up the live",
    r"if you could go back in time",
    r"kla harris or donald trump",
    r"who would you vote for",
    r"what'?s your birth year",
    r"and what month",
    r"how old are you",
    r"do you support donald trump",
    r"why (would|do) you support",
    r"why (would|do) you vote for",
    r"appreciate (it|you)",
    r"thank you (so much|for)",
    r"i have a few people to (thank|think)",
    r"let me let the",
    r"how'?s everybody doing",
]
PARKER_STRONG_RE = re.compile("|".join(PARKER_STRONG), re.IGNORECASE)

PARKER_MODERATE = [
    r"^for sure\.?$",
    r"^okay\.?\s*(for sure|um|so|and)?\.?$",
    r"^yo,? what'?s up",
    r"^hello\.?$",
    r"what do you (think|mean|say)",
    r"can (you|i) (explain|ask)",
    r"(studies|data|research) (show|say|indicate|suggest)",
]
PARKER_MODERATE_RE = re.compile("|".join(PARKER_MODERATE), re.IGNORECASE)


def merge_utterances(segments):
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
                utterances.append({"start": current_start, "end": current_end, "text": " ".join(current_texts)})
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
                utterances.append({"start": current_start, "end": current_end, "text": " ".join(current_texts)})
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
        utterances.append({"start": current_start, "end": current_end, "text": " ".join(current_texts)})
    return utterances


def score_parker(text):
    score = 0.0
    text_lower = text.lower().strip()
    if PARKER_STRONG_RE.search(text_lower):
        score += 3.0
    if PARKER_MODERATE_RE.search(text_lower):
        score += 1.5
    question_count = text.count("?")
    if question_count > 0:
        score += 0.3 * question_count
    policy_words = ["policy", "bipartisan", "legislation", "progressive", "conservative",
                    "statistic", "percent", "billion", "according to", "studies show"]
    for pw in policy_words:
        if pw in text_lower:
            score += 0.2
    word_count = len(text_lower.split())
    if word_count <= 3:
        score -= 0.5
    return score


def detect_guest_chapters(utterances):
    chapters = []
    current_chapter_start = 0
    chapter_num = 0
    intro_re = re.compile(
        r"what'?s your birth year|how old are you|do you support (donald|trump)|"
        r"who did you vote for|welcome to the stream|what'?s your name", re.IGNORECASE)
    for i, utt in enumerate(utterances):
        is_intro = intro_re.search(utt["text"])
        big_gap = i > 0 and (utt["start"] - utterances[i-1]["end"]) > 60
        if (is_intro or big_gap) and i > 5:
            if current_chapter_start < i:
                chapters.append({
                    "chapter": chapter_num, "start_idx": current_chapter_start,
                    "end_idx": i - 1, "start_time": utterances[current_chapter_start]["start"],
                    "end_time": utterances[i-1]["end"],
                })
                chapter_num += 1
                current_chapter_start = i
    if current_chapter_start < len(utterances):
        chapters.append({
            "chapter": chapter_num, "start_idx": current_chapter_start,
            "end_idx": len(utterances) - 1, "start_time": utterances[current_chapter_start]["start"],
            "end_time": utterances[-1]["end"],
        })
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


def label_speakers_v3(utterances, chapters):
    if not utterances:
        return utterances
    utt_to_chapter = {}
    for ch in chapters:
        for idx in range(ch["start_idx"], ch["end_idx"] + 1):
            utt_to_chapter[idx] = ch["chapter"]
    scores = [score_parker(u["text"]) for u in utterances]

    # HYBRID: use >> alternation as baseline, override only on strong signal
    prev_speaker = "parker"
    for i, utt in enumerate(utterances):
        ch_num = utt_to_chapter.get(i, 0)
        guest_label = "guest_%d" % max(ch_num, 1)
        score = scores[i]

        # What would alternating say?
        if i == 0:
            toggle = "parker"
        elif prev_speaker == "parker":
            toggle = guest_label
        else:
            toggle = "parker"

        # Strong content override
        if score >= 2.0:
            utt["speaker"] = "parker"
            utt["speaker_confidence"] = "high"
        elif score >= 1.0 and toggle != "parker":
            # Moderate Parker signal overrides toggle-to-guest
            utt["speaker"] = "parker"
            utt["speaker_confidence"] = "medium"
        else:
            # Trust the toggle
            if toggle == "parker":
                utt["speaker"] = "parker"
            else:
                utt["speaker"] = guest_label
            utt["speaker_confidence"] = "low"

        prev_speaker = utt["speaker"]

    return utterances


def fmt_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def structure_transcript(raw_path, output_dir):
    with open(raw_path) as f:
        raw = json.load(f)
    print("Structuring: %s" % raw["title"])
    print("  Raw segments: %d" % raw["segment_count"])
    utterances = merge_utterances(raw["segments"])
    print("  Merged into %d utterances" % len(utterances))
    chapters = detect_guest_chapters(utterances)
    print("  Detected %d chapters" % len(chapters))
    utterances = label_speakers_v3(utterances, chapters)
    speakers = sorted(set(u["speaker"] for u in utterances))
    parker_count = sum(1 for u in utterances if u["speaker"] == "parker")
    guest_speakers = [s for s in speakers if s != "parker"]
    from collections import Counter
    conf = Counter(u.get("speaker_confidence", "?") for u in utterances)
    print("  Speakers: parker (%d) + %d guests (%d utterances)" % (
        parker_count, len(guest_speakers), len(utterances) - parker_count))
    print("  Confidence: %s" % ", ".join("%s=%d" % (k, v) for k, v in sorted(conf.items())))
    for ch in chapters:
        dur = ch["end_time"] - ch["start_time"]
        ch_speakers = set()
        for idx in range(ch["start_idx"], ch["end_idx"] + 1):
            if idx < len(utterances) and utterances[idx]["speaker"] != "parker":
                ch_speakers.add(utterances[idx]["speaker"])
        spk_str = ", ".join(sorted(ch_speakers)) if ch_speakers else "intro"
        print("    Ch%d: %s - %s (%dm) [%s]" % (
            ch["chapter"], fmt_ts(ch["start_time"]), fmt_ts(ch["end_time"]), dur / 60, spk_str))
    structured = {
        "video_id": raw["video_id"], "url": raw["url"], "title": raw["title"],
        "author": raw["author"], "is_auto_generated": raw["is_auto_generated"],
        "total_duration_sec": raw["total_duration_sec"],
        "utterance_count": len(utterances), "chapter_count": len(chapters),
        "speakers": speakers, "chapters": chapters, "utterances": utterances,
    }
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    out_path = "%s/%s.structured.json" % (output_dir, raw["video_id"])
    with open(out_path, "w") as f:
        json.dump(structured, f, indent=2, ensure_ascii=False)
    print("  Saved to %s" % out_path)
    return structured


def main():
    parser = argparse.ArgumentParser(description="Structure raw transcripts")
    parser.add_argument("raw_json", help="Path to raw JSON")
    parser.add_argument("--output", default="./data/structured", help="Output directory")
    args = parser.parse_args()
    structure_transcript(args.raw_json, args.output)


if __name__ == "__main__":
    main()
