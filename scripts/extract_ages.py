"""Extract caller age Q&A pairs from YouTube caption dumps (livestream VODs).

Heuristic: Parker asks "how old are you" -> the next self-age statement within
a short window is the caller's answer. Auto-captions have no speaker labels,
so pairing (not diarization) is the signal. Third-party age mentions ("five
year olds...") are filtered by requiring an answer after a question.

Usage:
    python scripts/extract_ages.py data/raw/*.json [--window 60] [--out data/derived/ages.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

Q_PAT = re.compile(
    r"(how old|what(?:'s| is) your age|your age\b|are you (\d{1,2})\b|"
    r"you(?:'re| are) (\d{1,2}) years)",
    re.I,
)
# Self-age statement: I'm 19 / I am 19 / I'm 19 years old / age is 19 / just turned 19
A_PAT = re.compile(
    r"\bI(?:'m| am| got| was like)?\s*(?:like\s*)?(\d{2})\b(?:\s*years?)?"
    r"|\b(\d{2})\s*years? old\b"
    r"|\bage(?:'s| is)\s*(\d{2})\b"
    r"|\bjust turned\s*(\d{2})\b",
    re.I,
)


def scan(video_path: Path, window: float) -> dict:
    data = json.loads(video_path.read_text())
    segs = [s for s in data.get("segments", []) if isinstance(s, dict) and s.get("text")]
    pairs, orphans_q = [], 0
    i = 0
    while i < len(segs):
        if Q_PAT.search(segs[i]["text"]):
            q_start = segs[i].get("start", 0) or 0
            q_text = segs[i]["text"].strip()
            answer = None
            j = i + 1
            while j < len(segs) and (segs[j].get("start", 0) or 0) - q_start <= window:
                m = A_PAT.search(segs[j]["text"])
                if m:
                    age = next(g for g in m.groups() if g)
                    if 10 <= int(age) <= 99:
                        answer = {
                            "age": int(age),
                            "answer_text": segs[j]["text"].strip()[:200],
                            "answer_start": segs[j].get("start"),
                            "seconds_after_q": round(
                                (segs[j].get("start", 0) or 0) - q_start, 1
                            ),
                        }
                        break
                j += 1
            if answer:
                pairs.append(
                    {
                        "question_text": q_text[:200],
                        "question_start": q_start,
                        **answer,
                    }
                )
                i = j + 1  # skip past the consumed answer
                continue
            else:
                orphans_q += 1
        i += 1

    ages = [p["age"] for p in pairs]
    return {
        "video_id": data.get("video_id", video_path.stem),
        "title": data.get("title"),
        "segments": len(segs),
        "pairs": pairs,
        "unanswered_questions": orphans_q,
        "ages": ages,
        "median_age": sorted(ages)[len(ages) // 2] if ages else None,
    }


def fmt_ts(s: float) -> str:
    s = int(s or 0)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--window", type=float, default=60.0)
    ap.add_argument("--out", type=Path, default=Path("data/derived/ages.json"))
    args = ap.parse_args()

    results = [scan(p, args.window) for p in args.inputs]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))

    all_ages = []
    for r in results:
        all_ages.extend(r["ages"])
        print(f"\n=== {r['video_id']}  ({r['title'] or 'untitled'}) ===")
        print(f"  answered: {len(r['pairs'])} | unanswered Qs: {r['unanswered_questions']}")
        print(f"  ages: {r['ages']}  median: {r['median_age']}")
        for p in r["pairs"][:4]:
            print(f"  [{fmt_ts(p['question_start'])}] Q: {p['question_text'][:90]}")
            print(f"             A: {p['age']}  ({p['answer_text'][:90]})")
    if all_ages:
        all_ages.sort()
        n = len(all_ages)
        print(f"\nTOTAL: {n} answered ages across {len(results)} videos")
        print(f"  median {all_ages[n // 2]} | range {all_ages[0]}-{all_ages[-1]}")
        bands = {"<18": 0, "18-24": 0, "25-34": 0, "35-49": 0, "50+": 0}
        for a in all_ages:
            b = "<18" if a < 18 else "18-24" if a < 25 else "25-34" if a < 35 else "35-49" if a < 50 else "50+"
            bands[b] += 1
        print(f"  bands: {bands}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
