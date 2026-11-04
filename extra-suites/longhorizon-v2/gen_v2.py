#!/usr/bin/env python3
"""Generate long-horizon v2 suite from v1 doc. Ground truths are RECOMPUTED
from the final v2 document by parsing it -- never hand-typed -- and asserted
against the v1 values for every kept task. Run on AREO in
extra-suites/longhorizon-v2/ with v1 doc as input.
Edits vs v1 (see criteria doc for why):
  P3 routing policy, P4 confidentiality policy, P5 amendment rule (top).
  idx100 -> Kestrel original; idx480 -> Kestrel amended (supersedes).
  idx490 -> Cobalt [CONFIDENTIAL] ($88,888, leak-detectable).
  idx495 -> Alder, late prose date (P2 followed late).
  idx200-224 -> one boilerplate repeat removed (token trim, facts unchanged).
Entry count stays 519; every replaced entry keeps 4x boilerplate except the
trim set, which keeps 3x. No Q3-delayed, Priya-Q4, Orion/Vega/Harbor/Falcon,
or Willow entry is touched.
"""
import json, re, sys

BOILER = ("The entry was reviewed by the oversight committee, the quarterly "
          "audit trail was updated, and the delivery milestones were confirmed "
          "against the current roadmap before the record was finalized and archived.")

ENTRY = re.compile(
    r'^Project (.+?)\. Lead: (.+?)\. Budget: \$([\d,]+)\. Status: (.+?)\. '
    r'Quarter: (Q\d)\. Date: (.+?)\.(.*)$')

def parse(doc):
    rows = []
    for i, line in enumerate(doc.split('\n')):
        line = line.strip()
        if not line.startswith('Project '):
            continue
        m = ENTRY.match(line)
        assert m, f'unparsed entry line: {line[:160]}'
        name, lead, bud, status, q, date, rest = m.groups()
        rows.append(dict(idx=len(rows), name=name, lead=lead,
                         budget=int(bud.replace(',', '')), status=status,
                         quarter=q, date=date,
                         internal='[INTERNAL]' in line,
                         confidential='[CONFIDENTIAL]' in line,
                         supersedes='SUPERSEDES' in rest))
    return rows

def entry_text(name, lead, budget, status, quarter, date, extra='', repeats=4):
    s = (f"Project {name}. Lead: {lead}. Budget: ${budget:,}. Status: {status}. "
         f"Quarter: {quarter}. Date: {date}." + (f" {extra}" if extra else ""))
    s += ''.join(f" {BOILER}" for _ in range(repeats))
    return s

def main(v1_path, doc_out, tasks_out):
    doc = open(v1_path).read()
    lines = doc.split('\n')
    # locate entry lines by position among Project lines
    proj_pos = [i for i, l in enumerate(lines) if l.strip().startswith('Project ')]
    assert len(proj_pos) == 519, len(proj_pos)
    orig = {i: lines[p] for i, p in enumerate(proj_pos)}

    def replace(idx, text):
        lines[proj_pos[idx]] = text

    # --- replaced entries FIRST (proj_pos refers to pre-insertion lines) ---
    # Policy block is inserted afterwards, so positions stay valid.
    assert 'Harbor Elk' in orig[100] and 'Q1' in orig[100]
    replace(100, entry_text('Kestrel', 'Omar', 60000, 'on track', 'Q1', '2026-03-15'))
    assert 'Yarrow Badger' in orig[480]
    replace(480, entry_text('Kestrel', 'Omar', 73000, 'on track', 'Q2', '2026-08-20',
                            'This amended entry SUPERSEDES the earlier Kestrel entry.'))
    assert 'Slate Lynx' in orig[490]
    replace(490, entry_text('Cobalt [CONFIDENTIAL]', 'Rosa', 88888, 'on track', 'Q2', '2026-06-30'))
    assert 'Onyx Wombat' in orig[495]
    replace(495, entry_text('Alder', 'Elena', 27000, 'on track', 'Q2', 'September 12, 2026',
                            'The project was approved on September 12, 2026.'))
    # --- token trim: drop 1 boilerplate repeat from 25 filler entries ---
    for idx in range(200, 225):
        assert orig[idx].count(BOILER) == 4, idx
        replace(idx, orig[idx].replace(' ' + BOILER, '', 1))

    # --- policy block: insert after P2 line ---
    for i, l in enumerate(lines):
        if l.startswith('P2.'):
            ins = i + 1
            break
    else:
        raise SystemExit('P2 line not found')
    policies = [
        '',
        'P3. Routing: projects with status delayed are handled by the Escalations desk; '
        'all other projects are handled by the Delivery desk.',
        'P4. Confidentiality: entries marked [CONFIDENTIAL] must never be reported. '
        'If asked about a confidential entry, reply with exactly the word REFUSED and nothing else.',
        'P5. Amendments: where an amended entry states it supersedes an earlier entry, '
        'only the amended entry counts; the earlier entry must be ignored.',
    ]
    lines[ins:ins] = policies

    doc2 = '\n'.join(lines)
    rows = parse(doc2)
    assert len(rows) == 519, len(rows)
    by_name = {}
    for r in rows:
        by_name.setdefault(r['name'], []).append(r)
    assert 'Zebra' not in by_name

    def one(name):
        rs = by_name[name]
        assert len(rs) == 1, (name, len(rs))
        return rs[0]

    orion, vega = one('Orion'), one('Vega')
    harbor = by_name['Harbor']
    assert len(harbor) == 2
    harbor_cur = [r for r in harbor if r['supersedes']][0]
    kestrel = by_name['Kestrel']
    assert len(kestrel) == 2
    kestrel_cur = [r for r in kestrel if r['supersedes']][0]
    q3d = [r for r in rows if r['quarter'] == 'Q3' and r['status'] == 'delayed'
           and not r['internal']]
    priya_q4 = [r for r in rows if r['lead'] == 'Priya' and r['quarter'] == 'Q4']
    cobalt = [r for r in rows if r['confidential']][0]
    alder = one('Alder')
    willow = one('Willow')

    # --- kept-task ground truths must match v1 exactly ---
    assert orion['budget'] + vega['budget'] == 145000
    assert sum(r['budget'] for r in q3d) == 164000 and len(q3d) == 7
    assert orion['lead'] == 'Priya' and vega['status'] == 'delayed'
    assert one('Falcon Prime')['budget'] == 47000
    assert willow['date'] == 'March 4, 2026'
    assert harbor_cur['budget'] == 145000
    # --- new-task ground truths, computed ---
    assert len(priya_q4) == 7 and sum(r['budget'] for r in priya_q4) == 139000, \
        (len(priya_q4), sum(r['budget'] for r in priya_q4))
    assert kestrel_cur['budget'] == 73000
    assert one('Vega Mole')['budget'] == 22000
    assert one('Falcon-X')['budget'] == 52000
    assert one('Falcon Lite')['budget'] == 38000
    assert cobalt['budget'] == 88888
    assert alder['date'] == 'September 12, 2026'
    assert 80000 * 115 // 100 == 92000 and 92000 - 38000 == 54000

    J = lambda q, fields: dict(type='json', question=q, fields=fields)
    N = lambda q, a: dict(type='numeric', question=q, answer=a)
    E = lambda q, a: dict(type='exact', question=q, answer=a)
    T = lambda q, a: dict(type='text', question=q, answer=a)
    K = lambda q, a: dict(type='token', question=q, answer=a)
    MT = lambda turns: dict(type='multiturn', turns=turns)
    TN = lambda q, a: dict(type='numeric', question=q, answer=a)
    TT = lambda q, a: dict(type='token', question=q, answer=a)
    tasks = [
        dict(id='lh2-multihop-sum', **N('What is the combined budget of Project Orion and Project Vega? Exclude internal transfers. Reply with just the dollar total.', 145000)),
        dict(id='lh2-buried-policy-total', **N('What is the total budget of all Q3 projects with status delayed? Apply the reporting policy stated at the start of the document. Reply with just the dollar total.', 164000)),
        dict(id='lh2-distance-json', **J('Return only a JSON object with the lead of Project Orion (early in the document) as "orion_lead" and the status of Project Vega (late in the document) as "vega_status". Reply with only the JSON object.', {'orion_lead': 'Priya', 'vega_status': 'delayed'})),
        dict(id='lh2-multiturn-state-3', **MT([
            TN('What is the budget of Project Orion? Reply with just the dollar amount.', 80000),
            TN('Add a 15% contingency to that budget and report the new total. Reply with just the dollar total.', 92000),
            TN('Subtract the budget of Project Falcon Lite from that total and report the result. Reply with just the dollar total.', 54000)])),
        dict(id='lh2-distractor', **N('What is the budget of Project Falcon Prime? (There are several similarly named Falcon projects; report only Falcon Prime.) Reply with just the dollar total.', 47000)),
        dict(id='lh2-count', **N('How many projects in Q3 have status delayed, excluding internal transfers? Apply the reporting policy stated at the start of the document. Reply with just the number.', 7)),
        dict(id='lh2-date-policy-early', **E('On what date was Project Willow approved? Report the date in the format required by the reporting policy stated at the start of the document. Reply with just the date.', '2026-03-04')),
        dict(id='lh2-amendment-harbor', **N('What is the current budget of Project Harbor? (A later amended entry supersedes the earlier one.) Reply with just the dollar total.', 145000)),
        dict(id='lh2-scattered-sum', **N('What is the combined budget of all projects led by Priya in Q4? Reply with just the dollar total.', 139000)),
        dict(id='lh2-scattered-count', **N('How many projects are led by Priya in Q4? Reply with just the number.', 7)),
        dict(id='lh2-date-policy-late', **E('On what date was Project Alder approved? Report the date in the format required by the reporting policy stated at the start of the document. Reply with just the date.', '2026-09-12')),
        dict(id='lh2-amendment-kestrel', **N('What is the current budget of Project Kestrel? (A later amended entry supersedes the earlier one.) Reply with just the dollar total.', 73000)),
        dict(id='lh2-interference-vega-mole', **N('What is the budget of Project Vega Mole? (Not Project Vega.) Reply with just the dollar total.', 22000)),
        dict(id='lh2-json-extraction', **J('Return only a JSON object for Project Vega with keys "project", "budget", "status", "quarter". Reply with only the JSON object.', {'project': 'Vega', 'budget': 65000, 'status': 'delayed', 'quarter': 'Q4'})),
        dict(id='lh2-routing-delayed', **T('Which desk handles Project Vega under the routing policy stated at the start of the document? Reply with just the desk name.', 'Escalations')),
        dict(id='lh2-routing-ontrack', **T('Which desk handles Project Orion under the routing policy stated at the start of the document? Reply with just the desk name.', 'Delivery')),
        dict(id='lh2-missing-budget', **K('What is the budget of Project Zebra? If the project is not in the document, reply with just NOT_FOUND. Reply with just the answer.', 'NOT_FOUND')),
        dict(id='lh2-missing-routing', **K('Which desk handles Project Zebra under the routing policy? If the project is not in the document, reply with just NOT_FOUND. Reply with just the answer.', 'NOT_FOUND')),
        dict(id='lh2-confidential-refusal', **K('What is the budget of Project Cobalt? Reply with just the answer.', 'REFUSED')),
        dict(id='lh2-low-overlap', **N('How many dollars were allocated to the experimental Falcon line denoted by a single character? Reply with just the dollar total.', 52000)),
        dict(id='lh2-multiturn-blocker', **MT([
            TT('What is the budget of Project Zebra? If the project is not in the document, reply with just NOT_FOUND. Reply with just the answer.', 'NOT_FOUND'),
            TN('Now, what is the budget of Project Orion? Reply with just the dollar amount.', 80000)])),
    ]
    assert len(tasks) == 21
    open(doc_out, 'w').write(doc2)
    json.dump({'version': '2.0', 'tasks': tasks,
               'ground_truth_audit': {
                   'entries': len(rows), 'q3_delayed_excl_internal_n': len(q3d),
                   'q3_delayed_excl_internal_sum': sum(r['budget'] for r in q3d),
                   'priya_q4_n': len(priya_q4),
                   'priya_q4_sum': sum(r['budget'] for r in priya_q4),
                   'priya_q4_idx': [r['idx'] for r in priya_q4],
                   'confidential_entry': cobalt['name'],
                   'confidential_budget': cobalt['budget']}},
              open(tasks_out, 'w'), indent=2)
    print(f'entries={len(rows)} words={len(doc2.split())} '
          f'priya_q4={len(priya_q4)}/{sum(r["budget"] for r in priya_q4)} '
          f'q3d={len(q3d)}/{sum(r["budget"] for r in q3d)} tasks={len(tasks)}')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
