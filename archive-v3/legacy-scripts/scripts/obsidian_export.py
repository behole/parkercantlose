#!/usr/bin/env python3
import sqlite3, os, sys

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'parker.db')
VAULT_PATH = '/home/behole/2026L/2026L/the-factory'
OUTPUT_DIR = os.path.join(VAULT_PATH, '01_Projects', 'Parker_Streams')

def format_ts(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f'{h}:{m:02d}:{s:02d}' if h > 0 else f'{m}:{s:02d}'

def yt_url(vid, sec):
    return f'https://youtu.be/{vid}?t={int(sec)}'

def export_video(video_id, output_dir=None, conn=None):
    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    own = conn is None
    if own:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
    video = conn.execute('SELECT * FROM videos WHERE video_id = ?', (video_id,)).fetchone()
    if not video:
        print(f'Video {video_id} not found')
        return
    chapters = conn.execute('SELECT * FROM chapters WHERE video_id = ? ORDER BY start_seconds', (video_id,)).fetchall()
    utterances = conn.execute('SELECT * FROM utterances WHERE video_id = ? ORDER BY start_seconds', (video_id,)).fetchall()
    L = []
    L.append('---')
    L.append(f'video_id: {video_id}')
    L.append(f'url: https://youtu.be/{video_id}')
    L.append('type: parker-stream')
    L.append(f'utterances: {video["utterance_count"]}')
    L.append(f'chapters: {video["chapter_count"]}')
    L.append('tags: [parker, livestream, debate]')
    L.append('---')
    L.append('')
    L.append(f'# Parker Livestream - {video_id}')
    L.append('')
    L.append(f'**Video:** [YouTube](https://youtu.be/{video_id})')
    L.append(f'**Utterances:** {video["utterance_count"]} | **Chapters:** {video["chapter_count"]}')
    L.append('')
    sub = [c for c in chapters if c['duration_seconds'] and c['duration_seconds'] > 120]
    brief = [c for c in chapters if not c['duration_seconds'] or c['duration_seconds'] <= 120]
    L.append('## Chapters')
    L.append('')
    for ch in sub:
        dm = ch['duration_seconds'] / 60
        ts = format_ts(ch['start_seconds'])
        url = yt_url(video_id, ch['start_seconds'])
        L.append(f'- **{ch["guest"]}** - [{ts}]({url}) ({dm:.0f} min, {ch["utterance_count"]} exchanges)')
    if brief:
        L.append(f'- *{len(brief)} brief exchanges (<2 min each)*')
    L.append('')
    L.append('## Detailed Transcript')
    L.append('')
    for ch in sub:
        dm = ch['duration_seconds'] / 60
        ts = format_ts(ch['start_seconds'])
        url = yt_url(video_id, ch['start_seconds'])
        L.append(f'### {ch["guest"]} - [{ts}]({url}) ({dm:.0f} min)')
        L.append('')
        ch_utts = [u for u in utterances if u['chapter_guest'] == ch['guest']]
        for u in ch_utts:
            uts = format_ts(u['start_seconds'])
            uu = yt_url(video_id, u['start_seconds'])
            t = u['text'][:500] + ' [...]' if len(u['text']) > 500 else u['text']
            sf = f'**{u["speaker"]}**' if u['speaker'] == 'Parker' else u['speaker']
            L.append(f'> [{uts}]({uu}) {sf}: {t}')
            L.append('>')
        L.append('')
    out = os.path.join(output_dir, f'Parker Stream - {video_id}.md')
    with open(out, 'w') as f:
        f.write(chr(10).join(L))
    print(f'Exported {video_id} -> {out}')
    print(f'  {len(sub)} detailed chapters, {len(brief)} brief exchanges')
    if own:
        conn.close()

def export_all(output_dir=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    vids = conn.execute('SELECT video_id FROM videos').fetchall()
    print(f'Exporting {len(vids)} videos...')
    for v in vids:
        export_video(v['video_id'], output_dir, conn)
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] != '--all':
        export_video(sys.argv[1])
    else:
        export_all()
