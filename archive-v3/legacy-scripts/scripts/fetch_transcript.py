#!/usr/bin/env python3
"""
Phase 1 - Ingest: Fetch YouTube transcript and save as raw JSON.
Uses youtube-transcript-api v1.2+ API (YouTubeTranscriptApi().fetch()).
"""
import json
import sys
import os
from datetime import datetime
from youtube_transcript_api import YouTubeTranscriptApi

def fetch_transcript(video_id, output_dir=None):
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
    os.makedirs(output_dir, exist_ok=True)

    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)

    segments = []
    for entry in transcript:
        segments.append({
            'text': entry.text,
            'start': entry.start,
            'duration': entry.duration,
        })

    result = {
        'video_id': video_id,
        'fetched_at': datetime.utcnow().isoformat(),
        'segment_count': len(segments),
        'segments': segments,
    }

    if segments:
        last = segments[-1]
        result['total_duration_seconds'] = last['start'] + last['duration']

    output_path = os.path.join(output_dir, f'{video_id}.json')
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Fetched {len(segments)} segments for {video_id}")
    print(f"Total duration: {result.get('total_duration_seconds', 0):.0f}s")
    print(f"Saved to: {output_path}")
    return result

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python fetch_transcript.py <video_id> [output_dir]")
        sys.exit(1)
    vid = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    fetch_transcript(vid, out)
