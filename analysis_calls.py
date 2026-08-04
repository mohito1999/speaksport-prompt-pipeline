import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = Path('/Users/mohitmotwani/Downloads/calls-2026-07-21-to-2026-08-04.csv')
OUT = Path('tmp/call_analysis')
OUT.mkdir(parents=True, exist_ok=True)

with SOURCE.open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

def compact(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def turns(text):
    # Transcripts use speaker labels in a few slightly different forms.
    parts = re.split(r'(?i)(?=(?:assistant|agent|ai|user|caller|customer)\s*:)', text or '')
    return [compact(p) for p in parts if compact(p)]

def speaker_turns(text):
    matches = list(re.finditer(r'(?i)(AI|assistant|agent|user|caller|customer)\s*:', text or ''))
    out = []
    for i, m in enumerate(matches):
        end = matches[i+1].start() if i + 1 < len(matches) else len(text)
        speaker = 'user' if m.group(1).lower() in {'user', 'caller', 'customer'} else 'ai'
        out.append((speaker, compact(text[m.end():end])))
    return out

HUMAN_REQ = re.compile(
    r"\b(transfer|connect|speak (?:to|with)|talk (?:to|with)|real person|live person|"
    r"representative|operator|somebody|someone|person please|pro\s*shop|golf\s*shop|"
    r"mccann|36 degrees|thirty[- ]?six degrees|snack shack|restaurant|extension)\b", re.I)

def classify_initiation(r):
    ts = speaker_turns(r['transcript'])
    users = [(i, t) for i, (s, t) in enumerate(ts) if s == 'user']
    ais = [(i, t) for i, (s, t) in enumerate(ts) if s == 'ai']
    first_human = next(((i, t) for i, t in users if HUMAN_REQ.search(t)), None)
    first_ai_offer = next(((i, t) for i, t in ais if re.search(r'\b(transfer|connect you|connect .*directly|golf shop team can|recommend contacting)\b', t, re.I)), None)
    if first_human and first_human[0] <= 3:
        return 'Caller requested human/destination immediately'
    if first_human and (not first_ai_offer or first_human[0] < first_ai_offer[0]):
        return 'Caller escalated after attempting self-service'
    if first_ai_offer:
        return 'AI initiated transfer due to a gap or routing need'
    return 'Unclear initiation'

def user_text(r):
    return ' '.join(t for s, t in speaker_turns(r['transcript']) if s == 'user').lower()

def classify_intent(r):
    u = user_text(r)
    t = compact(r['transcript']).lower()
    if re.search(r'lost|left my|forgot|found (?:a|my)|wallet|telephone|phone.*(?:restaurant|course)', u):
        return 'Lost and found'
    if re.search(r'cancel|cancellation', u):
        return 'Tee-time cancellation'
    if re.search(r'modif|change|move|resched|revise|edit reservation|add (?:a |one |1 )?player|reduce.*(?:player|foursome)|split.*(?:tee|time)|late for my|verify.*(?:tee|tea|key|time)|confirm.*(?:tee|tea|key|time)|check.*existing reservation|when is my.*(?:tee|tea|key|time)|did not (?:get|receive).*email|never sent.*email', u):
        return 'Existing booking modification or confirmation'
    if re.search(r'multiple (?:tee|tea|key|t)|(?:two|three|2|3) (?:separate |consecutive )?(?:tee|tea|key|t) ?times|consecutive|group of|(?:8|9|10|11|12|16|20|80) player|players.*(?:8|9|10|11|12|16|20)|tournament tee|groups of', u):
        return 'Group or multiple tee times'
    if re.search(r'green fee|how much|price|rate|cost|replay special|discount|coupon|promo', u):
        return 'Rates, pricing, and promotions'
    if re.search(r'mccann|36 degrees|30 6|3 36|restaurant|dinner|dining|lunch|pizza|menu|food|order|snack|bar and grill|slices|gift card.*(?:restaurant|dining)', u):
        return 'Dining and food service'
    if re.search(r'lesson|instructor|golf pro|teaching|clinic', u):
        return 'Golf lessons and instruction'
    if re.search(r'event|wedding|banquet|tournament|outing|sales coordinator|group sales', u):
        return 'Events and tournaments'
    if re.search(r'member|membership|billing|refund|credit|charge|receipt|merch|gift card|gift certificate|club fitting|vendor|job|employment|donation|sponsor|hr\b|licensing|owner of your business|door ?dash', u):
        return 'Membership, billing, retail, or administration'
    if re.search(r'greens|punched|aerat|course condition|cart path|frost|weather|range|driving range|practice|dress code|rental|club rental|pace|walking|cadd|hole|yardage|handicap|slope|course open|close|hours|twilight', u):
        return 'Course, practice facilities, and current conditions'
    if re.search(r'(book|reserve|availability|available|check|make).*(?:tee|tea|key|t |time)|(?:tee|tea|key|t) ?time|golf reservation|single.*(?:today|tomorrow)', u):
        return 'New tee-time booking or availability'
    if re.search(r'pro\s*shop|golf\s*shop|representative|real person|somebody|someone|operator|transfer|connect me', u):
        return 'Unspecified direct routing request'
    return 'Other / unclear'

def classify_lever(r, initiation, intent):
    u = user_text(r)
    t = compact(r['transcript']).lower()
    if initiation == 'Caller escalated after attempting self-service':
        return 'Conversation/UX improvement'
    if intent in {'Tee-time cancellation', 'Existing booking modification or confirmation', 'Group or multiple tee times', 'Lost and found'}:
        return 'Product or workflow capability'
    if intent in {'Rates, pricing, and promotions', 'Course, practice facilities, and current conditions'}:
        return 'Knowledge/data integration'
    if intent == 'New tee-time booking or availability' and initiation != 'Caller requested human/destination immediately':
        return 'Conversation/UX improvement'
    if initiation == 'Caller requested human/destination immediately' and intent in {'Unspecified direct routing request', 'New tee-time booking or availability'}:
        return 'Caller adoption / AI-first framing'
    if intent in {'Dining and food service', 'Events and tournaments', 'Golf lessons and instruction', 'Membership, billing, retail, or administration'}:
        return 'Appropriate specialist routing'
    return 'Case review / routing policy'

def destination(r):
    t = compact(r['transcript']).lower()
    matches = re.findall(r'transferring you to (?:the |our )?([^\.]+)', t)
    phrase = matches[-1] if matches else ''
    if re.search(r'pro\s*shop|golf\s*shop|clubhouse', phrase):
        return 'Golf shop / pro shop'
    if re.search(r'mccann', phrase):
        return "McCann's Bar & Grill"
    if re.search(r'36|degree north', phrase):
        return '36 Degrees North'
    if re.search(r'event|group sales|sales', phrase):
        return 'Events / group sales'
    if re.search(r'snack|slices', phrase):
        return 'Slices / snack bar'
    if re.search(r'food|beverage|james kellogg', phrase):
        return 'Food & beverage leadership'
    if re.search(r'manager|manny|sandra|activities|nicole|extension|member services|staff', phrase):
        return 'Named staff / administration'
    return 'Other / unclear destination'

forwarded = [r for r in rows if r['ended_reason'] == 'assistant-forwarded-call']
INTENT_OVERRIDES = {
    3: 'Group or multiple tee times', 11: 'Unspecified direct routing request',
    20: 'Group or multiple tee times', 28: 'Existing booking modification or confirmation',
    38: 'Unspecified direct routing request', 57: 'Existing booking modification or confirmation',
    59: 'Dining and food service', 64: 'Dining and food service',
    73: 'Existing booking modification or confirmation', 74: 'Membership, billing, retail, or administration',
    79: 'Existing booking modification or confirmation', 85: 'Unspecified direct routing request',
    86: 'Unspecified direct routing request', 92: 'Unspecified direct routing request',
    98: 'Dining and food service', 99: 'Group or multiple tee times',
    100: 'Dining and food service', 107: 'Events and tournaments',
    109: 'Group or multiple tee times', 119: 'Unspecified direct routing request',
    120: 'Dining and food service', 122: 'Existing booking modification or confirmation',
    123: 'Unspecified direct routing request', 125: 'Existing booking modification or confirmation',
    131: 'Dining and food service', 141: 'Membership, billing, retail, or administration',
    145: 'Existing booking modification or confirmation', 146: 'Membership, billing, retail, or administration',
    157: 'Existing booking modification or confirmation', 158: 'Existing booking modification or confirmation',
    160: 'Existing booking modification or confirmation', 164: 'Dining and food service',
    169: 'Unspecified direct routing request', 174: 'Membership, billing, retail, or administration',
    181: 'Unspecified direct routing request', 189: 'Events and tournaments',
    199: 'Unspecified direct routing request', 206: 'Existing booking modification or confirmation',
    211: 'Unspecified direct routing request', 220: 'Unspecified direct routing request',
    223: 'Dining and food service', 231: 'Membership, billing, retail, or administration',
    235: 'Group or multiple tee times', 238: 'Dining and food service',
    242: 'Dining and food service', 249: 'Unspecified direct routing request',
    254: 'Existing booking modification or confirmation', 256: 'Dining and food service',
    257: 'Existing booking modification or confirmation', 258: 'Existing booking modification or confirmation',
    265: 'Group or multiple tee times', 269: 'Dining and food service',
    270: 'Dining and food service', 273: 'Unspecified direct routing request',
    279: 'Membership, billing, retail, or administration', 288: 'Group or multiple tee times',
    291: 'Group or multiple tee times', 296: 'Existing booking modification or confirmation',
    298: 'Existing booking modification or confirmation', 299: 'Dining and food service',
    302: 'Dining and food service', 321: 'Rates, pricing, and promotions',
    322: 'Course, practice facilities, and current conditions', 324: 'New tee-time booking or availability',
    329: 'Membership, billing, retail, or administration', 330: 'Group or multiple tee times',
    335: 'Group or multiple tee times', 342: 'New tee-time booking or availability',
    351: 'Unspecified direct routing request', 353: 'Group or multiple tee times',
}
INITIATION_OVERRIDES = {
    4: 'Caller requested human/destination immediately',
    11: 'Caller requested human/destination immediately',
    38: 'Caller requested human/destination immediately',
    85: 'Caller requested human/destination immediately',
    86: 'Caller requested human/destination immediately',
    92: 'Caller requested human/destination immediately',
    119: 'Caller requested human/destination immediately',
    123: 'Caller requested human/destination immediately',
    169: 'Caller requested human/destination immediately',
    181: 'Caller requested human/destination immediately',
    199: 'Caller requested human/destination immediately',
    211: 'Caller requested human/destination immediately',
    220: 'Caller requested human/destination immediately',
    273: 'Caller requested human/destination immediately',
    319: 'Caller requested human/destination immediately',
    351: 'Caller requested human/destination immediately',
}
classified = []
for idx, r in enumerate(forwarded, 1):
    initiation = INITIATION_OVERRIDES.get(idx, classify_initiation(r))
    intent = INTENT_OVERRIDES.get(idx, classify_intent(r))
    lever = classify_lever(r, initiation, intent)
    st = speaker_turns(r['transcript'])
    classified.append({
        **r,
        'forward_index': idx,
        'initiation': initiation,
        'intent': intent,
        'primary_lever': lever,
        'destination': destination(r),
        'caller_utterances': ' | '.join(t for s, t in st if s == 'user'),
    })

# Write a compact, line-numbered corpus for systematic review.
with (OUT / 'forwarded_corpus.txt').open('w', encoding='utf-8') as f:
    for i, r in enumerate(forwarded, 1):
        f.write(f"\n===== FWD {i:03d} | {r['call_date']} {r['call_time']} | {r['duration']} | {r['call_id']} =====\n")
        f.write(compact(r['transcript']) + '\n')

with (OUT / 'all_calls_compact.csv').open('w', encoding='utf-8', newline='') as f:
    fields = list(rows[0]) + ['transcript_compact']
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow({**r, 'transcript_compact': compact(r['transcript'])})

with (OUT / 'forwarded_classified.csv').open('w', encoding='utf-8', newline='') as f:
    fields = list(classified[0])
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(classified)

with (OUT / 'review_lines.txt').open('w', encoding='utf-8') as f:
    for r in classified:
        f.write(f"{r['forward_index']:03d}\t{r['initiation']}\t{r['intent']}\t{r['primary_lever']}\t{r['caller_utterances']}\n")

print(json.dumps({
    'all_calls': len(rows),
    'forwarded': len(forwarded),
    'forward_rate': len(forwarded)/len(rows),
    'ended_reasons': Counter(r['ended_reason'] for r in rows),
    'date_counts': Counter(r['call_date'] for r in rows),
    'initiation': Counter(r['initiation'] for r in classified),
    'intent': Counter(r['intent'] for r in classified),
    'primary_lever': Counter(r['primary_lever'] for r in classified),
    'destination': Counter(r['destination'] for r in classified),
}, indent=2, default=dict))
