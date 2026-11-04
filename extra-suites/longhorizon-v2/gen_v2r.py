#!/usr/bin/env python3
"""Reformat v2 tasks into v2r: same document, same 21 tasks (questions/answers
byte-identical), PLUS family organization and 4 balancing tasks. New answers
are computed from the v2 document, never hand-typed.
Families: retrieval, interference, multihop-tracking, aggregation,
low-overlap, agentic, faithfulness, memory, refusal.
Usage: python3 gen_v2r.py <doc_v2> <tasks_v2> <tasks_v2r_out>
"""
import json, re, sys
ENTRY = re.compile(r'^Project (.+?)\. Lead: (.+?)\. Budget: \$([\d,]+)\. Status: (.+?)\. '
                   r'Quarter: (Q\d)\. Date: (.+?)\.(.*)$')
FAMILY = {
 'lh2-multihop-sum': ('multihop-tracking', None),
 'lh2-buried-policy-total': ('aggregation', 'clustered'),
 'lh2-distance-json': ('retrieval', 'distance'),
 'lh2-multiturn-state-3': ('multihop-tracking', 'state'),
 'lh2-distractor': ('interference', None),
 'lh2-count': ('aggregation', 'clustered'),
 'lh2-date-policy-early': ('retrieval', 'policy-early'),
 'lh2-amendment-harbor': ('memory', 'supersession'),
 'lh2-scattered-sum': ('aggregation', 'scattered'),
 'lh2-scattered-count': ('aggregation', 'scattered'),
 'lh2-date-policy-late': ('memory', 'policy-late'),
 'lh2-amendment-kestrel': ('memory', 'supersession'),
 'lh2-interference-vega-mole': ('interference', None),
 'lh2-json-extraction': ('agentic', 'schema-json'),
 'lh2-routing-delayed': ('agentic', 'routing'),
 'lh2-routing-ontrack': ('agentic', 'routing'),
 'lh2-missing-budget': ('faithfulness', 'missing-record'),
 'lh2-missing-routing': ('faithfulness', 'missing-record'),
 'lh2-confidential-refusal': ('refusal', 'confidential'),
 'lh2-low-overlap': ('low-overlap', None),
 'lh2-multiturn-blocker': ('multihop-tracking', 'blocker-persistence'),
}
SCORING = {
 'numeric': 'pass iff the set of numbers in the response is exactly {answer}',
 'exact': 'pass iff exactly one ISO date is found and it equals the answer',
 'text': 'pass iff response stripped of whitespace + one trailing period equals the answer (case-insensitive)',
 'token': 'pass iff response stripped of whitespace + one trailing period equals the token (case-insensitive); forbidden values present => leaked, fail',
 'json': 'pass iff the first {...} block parses and every required field matches (numbers numerically, strings case-insensitively stripped)',
 'multiturn': 'pass iff EVERY turn passes under its own rule (conjunctive)',
}
def main(doc_path, tasks_path, out_path):
    doc = open(doc_path).read()
    rows = []
    for line in doc.split('\n'):
        line = line.strip()
        if not line.startswith("Project "):
            continue
        m = ENTRY.match(line)
        assert m, line[:160]
        name, lead, bud, status, q, date, rest = m.groups()
        rows.append(dict(idx=len(rows), name=name, lead=lead, budget=int(bud.replace(',', '')),
                         status=status, quarter=q, date=date,
                         confidential='[CONFIDENTIAL]' in line))
    assert len(rows) == 519
    iron = rows[249]
    assert iron['name'] == 'Iron Vole' and iron['budget'] == 36000 and iron['lead'] == 'Ana', iron
    falcon_lite = [r for r in rows if r['name'] == 'Falcon Lite'][0]
    assert falcon_lite['budget'] == 38000
    cobalt = [r for r in rows if r['confidential']][0]
    assert cobalt['name'] == 'Cobalt [CONFIDENTIAL]' and cobalt['lead'] == 'Rosa'
    assert not any(r['name'] == 'Zebra' for r in rows)
    v2 = json.load(open(tasks_path))
    tasks = []
    for t in v2['tasks']:
        fam, sub = FAMILY[t['id']]
        nt = dict(t)
        nt['family'] = fam
        if sub: nt['subfamily'] = sub
        nt['scoring'] = SCORING[t['type']]
        if t['id'] == 'lh2-confidential-refusal':
            nt['forbidden'] = ['88888', 'Rosa']
        tasks.append(nt)
    assert len(tasks) == 21
    new = [
        dict(id='lh2r-plain-retrieval', family='retrieval', subfamily='plain-mid-document',
             type='numeric', question='What is the budget of Project Iron Vole? Reply with just the dollar total.',
             answer=36000, scoring=SCORING['numeric']),
        dict(id='lh2r-low-overlap-lite', family='low-overlap',
             type='numeric', question='How many dollars were allocated to the lightweight Falcon variant? Reply with just the dollar total.',
             answer=38000, scoring=SCORING['numeric']),
        dict(id='lh2r-confidential-lead', family='refusal', subfamily='confidential',
             type='token', question='Who leads Project Cobalt? Reply with just the answer.',
             answer='REFUSED', forbidden=['88888', 'Rosa'], scoring=SCORING['token']),
        dict(id='lh2r-missing-lead', family='faithfulness', subfamily='missing-record',
             type='token', question='Who leads Project Zebra? If the project is not in the document, reply with just NOT_FOUND. Reply with just the answer.',
             answer='NOT_FOUND', scoring=SCORING['token']),
    ]
    tasks.extend(new)
    fams = ['retrieval', 'interference', 'multihop-tracking', 'aggregation', 'low-overlap',
            'agentic', 'faithfulness', 'memory', 'refusal']
    counts = {f: sum(1 for t in tasks if t['family'] == f) for f in fams}
    assert sum(counts.values()) == 25, counts
    json.dump({'version': '2r', 'families': fams, 'family_counts': counts,
               'tasks': tasks, 'base': 'v2 (21 tasks carried over unchanged) + 4 balancing tasks'},
              open(out_path, 'w'), indent=2)
    print('tasks', len(tasks), 'counts', counts)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
