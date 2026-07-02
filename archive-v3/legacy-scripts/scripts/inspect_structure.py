#!/usr/bin/env python3
"""Inspect structured output quality."""
import json

with open("data/structured/JPBNQ1imn0E.json") as f:
    data = json.load(f)

print(f"=== SUMMARY ===")
print(f"Utterances: {data['total_utterances']}")
print(f"Chapters: {data['total_chapters']}")

# Show first 30 utterances with speakers
print(f"\n=== FIRST 30 UTTERANCES ===")
for u in data["utterances"][:30]:
    text_preview = u["text"][:80] + "..." if len(u["text"]) > 80 else u["text"]
    mins = u["start"] / 60
    print(f"  [{mins:5.1f}m] {u['speaker']:12s} | {text_preview}")

# Chapter duration distribution
print(f"\n=== CHAPTER DURATIONS ===")
durations = []
for ch in data["chapters"]:
    dur = (ch["end"] - ch["start"]) / 60 if ch["end"] else 0
    durations.append(dur)

short = sum(1 for d in durations if d < 1)
medium = sum(1 for d in durations if 1 <= d < 15)
long = sum(1 for d in durations if d >= 15)
print(f"  < 1 min: {short} chapters (likely brief/false)")
print(f"  1-15 min: {medium} chapters")  
print(f"  15+ min: {long} chapters (long debates)")

# Show the substantial chapters
print(f"\n=== SUBSTANTIAL CHAPTERS (>2min) ===")
for ch in data["chapters"]:
    dur = (ch["end"] - ch["start"]) / 60 if ch["end"] else 0
    if dur > 2:
        start_m = ch["start"] / 60
        print(f"  {ch['guest']:12s}: {start_m:.0f}m - {start_m+dur:.0f}m ({dur:.1f}min, {ch['utterance_count']} utterances)")
