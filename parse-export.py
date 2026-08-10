#!/usr/bin/env python3
"""
Parse WhatsApp export into cards. Reads every line, groups multi-line messages,
then groups consecutive same-sender messages into devotional cards.
Extracts: YouTube links, images, Telugu verses, English verses.
"""

import json, re, shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

EXPORT = Path.home() / 'fellowship-in-jesus-christ' / '_whatsapp-export'
CHAT = EXPORT / '_chat.txt'
OUT = Path.home() / 'fellowship-in-jesus-christ' / 'messages.json'
ASSETS = Path.home() / 'fellowship-in-jesus-christ' / 'assets'

# ── Patterns ──────────────────────────────────────
MSG_HEAD = re.compile(r'^\[(\d+/\d+/\d+),\s*(\d+:\d+:\d+)\s*(?:[APap][Mm])?\]\s+(.+?):\s+(.*)')
YT = re.compile(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w\-]+)')
IMG = re.compile(r'<attached:\s*([^>]+\.(?:jpg|jpeg|png|gif|webp|heic))>', re.I)
VID = re.compile(r'<attached:\s*([^>]+\.(?:mp4|mov|mkv))>', re.I)
VERSE_REF = re.compile(r'([\w\s]+)\s+(\d+)\s*:\s*(\d+(?:[-–]\d+)?)')
TELUGU = re.compile(r'[\u0C00-\u0C7F]')
SYSTEM_SKIP = re.compile(r'Messages and calls are end-to-end|Group creator|were added|changed the|changed this|security code')

# ── Parse to messages ─────────────────────────────
def parse_messages():
    lines = CHAT.read_text(encoding='utf-8').splitlines()
    messages = []
    current = None
    
    for line in lines:
        line = line.replace('\u200e', '').replace('\u202f', ' ')
        m = MSG_HEAD.match(line)
        
        if m:
            if current:
                messages.append(current)
            
            date, time, sender, text = m.group(1), m.group(2), m.group(3).strip(), m.group(4)
            current = {
                'date': date, 'time': time,
                'sender': sender,
                'lines': [text] if text else []
            }
        elif current:
            current['lines'].append(line)
    
    if current:
        messages.append(current)
    
    return messages

# ── Parse datetime ─────────────────────────────────
def to_dt(date, time):
    try:
        parts = date.split('/')
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        if y < 100: y += 2000
        t = time.split(':')
        h, mi, s = int(t[0]), int(t[1]), int(t[2]) if len(t) > 2 else 0
        return datetime(y, m, d, h, mi, s, tzinfo=timezone.utc)
    except:
        return datetime(2000,1,1, tzinfo=timezone.utc)

# ── Group into cards ──────────────────────────────
def group_cards(messages):
    cards = []
    cur = None
    
    for msg in messages:
        text = '\n'.join(msg['lines']).strip()
        
        # Skip system/deleted
        if 'This message was deleted' in text:
            continue
        if SYSTEM_SKIP.search(text):
            continue
        if not text:
            continue
        
        dt = to_dt(msg['date'], msg['time'])
        sender = msg['sender']
        
        # Start new card if: sender changed OR gap > 45 min
        if cur and (cur['sender'] != sender or (dt - cur['last_dt']) > timedelta(minutes=45)):
            cards.append(finalize(cur))
            cur = None
        
        if not cur:
            cur = {
                'sender': sender,
                'first_dt': dt,
                'last_dt': dt,
                'texts': [],
                'images': [],
                'youtube_url': None,
                'youtube_title': None,
            }
        else:
            cur['last_dt'] = dt
        
        # Extract media
        yt = YT.search(text)
        if yt and not cur['youtube_url']:
            cur['youtube_url'] = yt.group(1)
        
        # Check first line for title
        first_line = text.split('\n')[0].strip()
        if yt and yt.group(1) in first_line:
            title = first_line.replace(yt.group(1), '').strip()
            if title and len(title) < 120:
                cur['youtube_title'] = title
        
        imgs = IMG.findall(text)
        for img in imgs:
            src = EXPORT / img
            if src.exists() and img not in cur['images']:
                dest = ASSETS / img
                if not dest.exists():
                    shutil.copy2(src, dest)
                cur['images'].append(f'assets/{img}')
        
        # Clean text
        clean = IMG.sub('', text)
        clean = VID.sub('', clean)
        clean = clean.strip()
        
        if clean:
            cur['texts'].append(clean)
    
    if cur:
        cards.append(finalize(cur))
    
    return cards

# ── Finalize card ────────────────────────────────
def finalize(cur):
    all_text = '\n\n'.join(cur['texts'])
    
    doc = {
        'date': cur['first_dt'].isoformat(),
        'sender': cur['sender'],
    }
    
    # Separate English and Telugu
    en_parts = []
    te_parts = []
    
    for t in cur['texts']:
        has_te = bool(TELUGU.search(t))
        has_en = bool(re.search(r'[A-Za-z]{20,}', t))
        if has_te and not has_en:
            te_parts.append(t)
        elif has_en and not has_te:
            en_parts.append(t)
        elif has_te and has_en:
            # Mixed — split by prevalence
            te_chars = len(TELUGU.findall(t))
            if te_chars > len(t) * 0.3:
                te_parts.append(t)
            else:
                en_parts.append(t)
        else:
            en_parts.append(t)
    
    # Clean verse text: remove the verse reference header line, separator lines
    def clean_verse(text):
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line = line.strip()
            if not line: continue
            if VERSE_REF.match(line): continue  # reference header line
            if re.match(r'^[≠=≈]', line): continue  # separator
            if line.startswith('http'): continue  # URLs
            cleaned.append(line)
        return '\n'.join(cleaned)
    
    en_verse = clean_verse('\n\n'.join(en_parts)).strip()
    te_verse = clean_verse('\n\n'.join(te_parts)).strip()
    
    if en_verse:
        doc['verse_english'] = en_verse[:600]
    if te_verse:
        doc['verse_telugu'] = te_verse[:600]
    
    # Extract verse reference
    for t in cur['texts']:
        vr = VERSE_REF.search(t)
        if vr:
            doc['verse_ref'] = vr.group(0).strip()
            # Use as topic
            doc['topic'] = vr.group(0).strip()
            break
    
    # YouTube
    if cur['youtube_url']:
        doc['youtube_url'] = cur['youtube_url']
    if cur.get('youtube_title'):
        doc['youtube_title'] = cur['youtube_title']
    
    # Image
    if cur['images']:
        doc['image'] = cur['images'][0]
    
    # Generate ID
    doc['id'] = f"card-{cur['first_dt'].strftime('%Y%m%d-%H%M%S')}"
    
    return doc

# ── Main ──────────────────────────────────────────
def main():
    ASSETS.mkdir(exist_ok=True)
    
    print("Parsing messages...")
    msgs = parse_messages()
    print(f"  {len(msgs)} messages found")
    
    # Filter: only Pops and Mom (real content)
    real = [m for m in msgs if m['sender'] in ('Pops', 'Mom', 'Dad', 'Amma')]
    print(f"  {len(real)} from family")
    
    print("Grouping into cards...")
    cards = group_cards(real)
    print(f"  {len(cards)} cards created")
    
    # Sort newest first
    cards.sort(key=lambda c: c['date'], reverse=True)
    
    # Extract all songs
    songs = []
    for c in cards:
        if c.get('youtube_url'):
            songs.append({
                'url': c['youtube_url'],
                'title': c.get('youtube_title', c.get('topic', 'Worship Song')),
                'date': c['date'],
            })
    
    # Remove songs from devotional cards (they go in separate section)
    for c in cards:
        c.pop('youtube_url', None)
        c.pop('youtube_title', None)
    
    output = {
        'group_name': 'Fellowship in Jesus Christ',
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'devotionals': cards,
        'songs': songs,
    }
    
    OUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    
    print(f"\nDone: {len(cards)} devotionals, {len(songs)} songs")
    print(f"Output: {OUT}")
    print(f"Assets: {ASSETS}")

if __name__ == '__main__':
    main()
