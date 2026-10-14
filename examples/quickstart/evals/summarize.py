"""Summarize all paired pilot trials without treating numeric screening as full QA."""
import argparse
import csv
import json
from pathlib import Path
import statistics

FIELDS=['total_tokens','inputTokens','cacheCreationInputTokens','cacheReadInputTokens','outputTokens','cost_usd','wall_seconds','tool_calls']

def summarize(rows):
    result={}
    models={m for r in rows for m in r['models']}
    if len(models)!=1: raise ValueError(f'Expected exactly one observed model, found {models}')
    for condition in ('semantic','recipe'):
        group=[r for r in rows if r['condition']==condition]
        if not group: raise ValueError(f'Missing condition {condition}')
        result[condition]={'trials':len(group),'completed':sum(r['completed'] for r in group),
            'numeric_screen_passes':sum(r['numeric_screen'] for r in group),
            'median':{key:statistics.median(r[key] for r in group if r[key] is not None) for key in FIELDS},
            'total_cost_usd':sum(r['cost_usd'] or 0 for r in group)}
    pairs={(r['case'],r['repeat']) for r in rows}
    if any(len([r for r in rows if (r['case'],r['repeat'])==pair])!=2 or
           {r['condition'] for r in rows if (r['case'],r['repeat'])==pair} != {'semantic','recipe'} for pair in pairs):
        raise ValueError('Incomplete pairs; wait for both conditions')
    result['model']=next(iter(models))
    result['paired_median_change_percent']={key:statistics.median(
        (next(r[key] for r in rows if (r['case'],r['repeat'])==pair and r['condition']=='recipe') /
         next(r[key] for r in rows if (r['case'],r['repeat'])==pair and r['condition']=='semantic')-1)*100
        for pair in pairs) for key in ('total_tokens','cost_usd','wall_seconds')}
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);args=ap.parse_args()
    rows=json.loads((args.directory/'metrics.json').read_text())
    protocol=json.loads((args.directory/'protocol.json').read_text())
    if len(rows)!=len(protocol['cases'])*protocol['repeats']*2: raise ValueError('Experiment is incomplete')
    summary=summarize(rows)
    (args.directory/'aggregate.json').write_text(json.dumps(summary,indent=2)+'\n')
    fields=['condition','case','repeat','completed','numeric_screen',*FIELDS]
    with (args.directory/'metrics.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
