#!/usr/bin/env python3
"""Inspect segments to understand speaker change patterns."""
import json
import sys

with open("data/raw/JPBNQ1imn0E.json") as f:
    data = json.load(f)

segments = data["segments"]
print(f"Total segments: {len(segments)}")

# Find speaker change markers
changes = []
for i, seg in enumerate(segments):
    if ">>" in seg["text"]:
        changes.append(i)

print(f"Segments with '>>': {len(changes)}")
print()

# Show first 15 speaker changes with context
for idx in changes[:15]:
    seg = segments[idx]
    print(f"[{idx}] @{seg['start']:.1f}s: {seg['text']!r}")

print("\n--- Sample continuous block (segments 0-20) ---")
for i in range(min(20, len(segments))):
    seg = segments[i]
    marker = " <<CHANGE>>" if ">>" in seg["text"] else ""
    print(f"[{i}] @{seg['start']:.1f}s ({seg['duration']:.1f}s): {seg['text']!r}{marker}")
