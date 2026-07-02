#!/usr/bin/env python3
"""
Phase 2 - Structure: Merge caption fragments into utterances, tag speakers.

Logic:
- Segments before first '>>' are Parker's intro
- '>>' marks a speaker change
- Alternating speakers: Parker asks questions, guest responds
- We track speaker changes to assign Parker vs Guest_N
- Utterances are groups of consecutive segments by the same speaker
"""
import json
import sys
import os
import re

def structure_transcript(input_path, output_path=None):
    with open(input_path) as f:
        data = json.load(f)

    segments = data["segments"]
    video_id = data["video_id"]

    if output_path is None:
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'structured')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f'{video_id}.json')

    # Phase 1: Build utterances by grouping segments between >> markers
    utterances = []
    current_segments = []
    current_start = None

    for seg in segments:
        text = seg["text"]
        if ">>" in text:
            # Save current utterance if any
            if current_segments:
                merged_text = " ".join(s["text"] for s in current_segments)
                utterances.append({
                    "start": current_start,
                    "end": current_segments[-1]["start"] + current_segments[-1]["duration"],
                    "text": merged_text.strip(),
                    "segment_indices": [s["_idx"] for s in current_segments],
                })
                current_segments = []

            # Start new utterance - strip the >> marker
            text_clean = text.replace(">>", "").strip()
            if text_clean:
                seg_copy = dict(seg)
                seg_copy["text"] = text_clean
                current_segments = [seg_copy]
                current_start = seg["start"]
        else:
            if not current_segments:
                current_start = seg["start"]
            current_segments.append(seg)

    # Don't forget the last utterance
    if current_segments:
        merged_text = " ".join(s["text"] for s in current_segments)
        utterances.append({
            "start": current_start,
            "end": current_segments[-1]["start"] + current_segments[-1]["duration"],
            "text": merged_text.strip(),
            "segment_indices": [],
        })

    # Phase 2: Assign speakers
    # First utterance block (before any >>) is Parker's intro
    # After that, >> alternates between guest and Parker
    # Heuristic: Parker tends to ask short questions and transition phrases
    # Guests tend to give longer answers
    # But the simplest model: odd >> = new speaker, even >> = back to Parker
    
    # Better approach: detect guest boundaries
    # Parker phrases: "let's go to the next", "how old are you", "do you support"
    parker_transition_patterns = [
        r"let'?s go (to |on )?the next",
        r"how old are you",
        r"do you support",
        r"all right[y]?",
        r"okay.*let'?s",
        r"next individual",
        r"next person",
    ]
    
    guest_num = 0
    is_parker = True  # Start with Parker (intro)
    speaker_change_count = 0
    
    for i, utt in enumerate(utterances):
        # Check if this is the first utterance (Parker's intro, before any >>)
        if i == 0 and not any(">>" in s["text"] for s in segments[:10]):
            utt["speaker"] = "Parker"
            continue
        
        # Toggle speaker on each utterance (since they're split by >>)
        if i > 0:
            # Check if Parker is transitioning to a new guest
            prev_text = utterances[i-1]["text"].lower()
            is_new_guest_transition = any(
                re.search(p, prev_text) for p in parker_transition_patterns
            )
            
            if is_new_guest_transition and is_parker:
                guest_num += 1
            
            is_parker = not is_parker
        
        if is_parker:
            utt["speaker"] = "Parker"
        else:
            utt["speaker"] = f"Guest_{guest_num}" if guest_num > 0 else "Guest_1"
    
    # Phase 3: Detect chapters (guest conversations)
    chapters = []
    current_chapter = None
    
    for utt in utterances:
        if utt["speaker"].startswith("Guest_"):
            guest_id = utt["speaker"]
            if current_chapter is None or current_chapter["guest"] != guest_id:
                if current_chapter:
                    current_chapter["end"] = utt["start"]
                    chapters.append(current_chapter)
                current_chapter = {
                    "guest": guest_id,
                    "start": utt["start"],
                    "end": None,
                    "utterance_count": 0,
                }
            current_chapter["utterance_count"] += 1
        elif current_chapter:
            current_chapter["utterance_count"] += 1
    
    if current_chapter:
        current_chapter["end"] = utterances[-1]["end"]
        chapters.append(current_chapter)

    # Build result
    result = {
        "video_id": video_id,
        "total_utterances": len(utterances),
        "total_chapters": len(chapters),
        "speakers": list(set(u["speaker"] for u in utterances)),
        "chapters": chapters,
        "utterances": utterances,
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    # Stats
    print(f"Structured {video_id}:")
    print(f"  Utterances: {len(utterances)}")
    print(f"  Chapters: {len(chapters)}")
    print(f"  Speakers: {len(result['speakers'])}")
    
    # Show chapter summary
    for ch in chapters[:10]:
        duration = (ch["end"] - ch["start"]) if ch["end"] else 0
        mins = duration / 60
        print(f"  {ch['guest']}: {mins:.1f}min ({ch['utterance_count']} utterances)")
    if len(chapters) > 10:
        print(f"  ... and {len(chapters) - 10} more chapters")
    
    print(f"Saved to: {output_path}")
    return result

if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default to the known video
        input_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'JPBNQ1imn0E.json')
    else:
        input_path = sys.argv[1]
    
    out = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Add index to segments for tracking
    with open(input_path) as f:
        d = json.load(f)
    for i, s in enumerate(d["segments"]):
        s["_idx"] = i
    # Write back temporarily
    with open(input_path, 'w') as f:
        json.dump(d, f, indent=2)
    
    structure_transcript(input_path, out)
