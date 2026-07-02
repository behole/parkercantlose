#!/usr/bin/env python3
import traceback

log = open("/home/behole/parker-pipeline/debug_output.txt", "w")

def p(msg):
    log.write(str(msg) + "\n")
    log.flush()

p("Starting...")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    p("Imported OK")
    api = YouTubeTranscriptApi()
    p("Created API instance")
    transcript = api.fetch("JPBNQ1imn0E")
    p(f"Fetch returned: {type(transcript)}")
    count = 0
    for entry in transcript:
        if count == 0:
            p(f"First entry type: {type(entry)}")
            p(f"First entry repr: {repr(entry)}")
            try:
                p(f"  .text = {entry.text}")
                p(f"  .start = {entry.start}")
                p(f"  .duration = {entry.duration}")
            except:
                p("  attribute access failed")
        count += 1
    p(f"Total segments: {count}")
except Exception as e:
    p(f"EXCEPTION: {type(e).__name__}: {e}")
    p(traceback.format_exc())

log.close()
