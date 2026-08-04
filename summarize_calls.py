import csv
from collections import Counter

classified = list(csv.DictReader(open('tmp/call_analysis/forwarded_classified.csv', encoding='utf-8')))
all_calls = list(csv.DictReader(open('/Users/mohitmotwani/Downloads/calls-2026-07-21-to-2026-08-04.csv', encoding='utf-8-sig')))
pro = [x for x in classified if x['destination'] == 'Golf shop / pro shop']

print('PRO', len(pro), f'{len(pro)/len(all_calls):.1%} of all; {len(pro)/len(classified):.1%} of forwarded')
for field in ['initiation', 'intent', 'primary_lever']:
    print('\n' + field)
    for k, v in Counter(x[field] for x in pro).most_common():
        print(k, v, f'{v/len(pro):.1%} pro', f'{v/len(all_calls):.1%} all')

print('\nALL FORWARDED INTENT')
for k, v in Counter(x['intent'] for x in classified).most_common():
    print(k, v, f'{v/len(classified):.1%} fwd', f'{v/len(all_calls):.1%} all')

print('\nBY DATE: all forwarded fwd_rate pro pro_rate')
for d in sorted(set(x['call_date'] for x in all_calls)):
    a = sum(x['call_date'] == d for x in all_calls)
    f = sum(x['call_date'] == d for x in classified)
    p = sum(x['call_date'] == d for x in pro)
    print(d, a, f, f'{f/a:.1%}', p, f'{p/a:.1%}')

print('\nCANCELLATION DATES')
cancel = [x for x in classified if x['intent'] == 'Tee-time cancellation']
print(Counter(x['call_date'] for x in cancel))

print('\nPRO X INITIATION/INTENT')
for intent, n in Counter(x['intent'] for x in pro).most_common():
    row = Counter(x['initiation'] for x in pro if x['intent'] == intent)
    print(intent, n, dict(row))

print('\nDURATION')
for label, group in [('all', all_calls), ('forwarded', classified), ('pro', pro), ('contained', [x for x in all_calls if x['ended_reason'] != 'assistant-forwarded-call'])]:
    vals = sorted(int(x['duration_ms'])/1000 for x in group)
    mean = sum(vals)/len(vals)
    med = vals[len(vals)//2]
    print(label, len(vals), f'mean={mean:.1f}s', f'median={med:.1f}s', f'total_hours={sum(vals)/3600:.2f}')
