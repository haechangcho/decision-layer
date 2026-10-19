"""Live Claude Code -> stdio MCP -> canonical API -> existing sample Cube.

Uses installed Claude authentication; never reads or logs credentials. Only the
Decision Layer MCP is available to the client. Requires the complete-journey demo.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[3]


def call(base,path,body=None,method=None):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(request,timeout=45) as response:return json.load(response)


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--api',default='http://localhost:8000')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=600)
    parser.add_argument('--failure-case',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    import sys
    sys.path.insert(0,str(ROOT))
    from examples.recipes.skill_chain import legacy_campaign_recipe as campaign_recipe
    recipe=campaign_recipe().model_dump(mode='json')
    catalog=call(args.api,'/semantic/catalog')
    refs={obj['ref'] for obj in catalog['objects']}
    required={ref for step in recipe['steps'] for value in step['bindings'].values() for ref in (value if isinstance(value,list) else [value])}
    if not required <= refs:raise RuntimeError('Required actual sample Cube refs are missing')
    call(args.api,'/recipes:validate?live=true',recipe)
    existing=next((r for r in call(args.api,'/recipes') if r['name']==recipe['name']),None)
    if not existing:
        call(args.api,'/recipes/'+recipe['name'],{'recipe':recipe,'base_version':None},'PUT')
    elif existing != recipe:
        # Do not silently overwrite reviewed assets.
        raise RuntimeError('Recipe already exists with different contents; inspect it before retrying')
    config={'mcpServers':{'decisionlayer':{'command':str(ROOT/'.venv/bin/decision-layer-mcp'),
        'env':{'DL_API_URL':args.api,'DL_WEB_URL':'http://localhost:3000','DL_LOCALE':'en'}}}}
    (out/'mcp.json').write_text(json.dumps(config,indent=2)+'\n')
    prompt='''Run the saved campaign-skill-investigation Recipe against the connected sample Cube for campaign start dates 2001-01-01 through 2001-12-31. This is a descriptive workflow experiment, not a causal study. Inspect actual definitions and discover the time dimension first. Use the Recipe as written. In the first Skill query campaign-level mean subsequent sales, sort descending, and select the highest returned campaign. For this execution experiment only, ties must be resolved by the smallest numeric campaign ID; explicitly record this supplied arbitrary tie-break rule, not a statistical finding. In the peer Skill query the selected subject and then other accessible campaigns excluding that subject, using identical period and scope; query peers by campaign and select the highest returned peer campaign using that same explicit tie-break rule for the registered household regression. Acknowledge that other campaigns are not risk-adjusted comparable peers. Let the server execute the Python stage; do not use local code or substitute old query.drilldown/query.peer_comparison. Inspect query logs, exported filters and final Python checks. Finish the same Run with evidence-linked findings and limitations, and give the Run link. Reading Skill text is not a validation pass. Record goals with no required capabilities unless a discovered contract actually certifies them.'''
    if args.failure_case:
        prompt += ''' Additionally, as an explicit failure-logging test, submit exactly one first-stage query with the incorrect 2000-01-01 through 2000-12-31 dates and current period_role. Expect rejection; use get_skill_query to read the persisted failed query record, then correct the dates using a NEW query ID. Do not change Run scope. This intentional invalid read must not reach Cube. Continue the normal workflow after the correction.'''
    system='You are testing a governed analysis workflow. Use only the supplied Decision Layer MCP. Do not access local files, shell, web, other agents or external communication tools. Follow the active Skill step instructions; AGENT_EXECUTION_REQUIRED means you must call run_skill_query and finish_skill_step, not ask the user to operate tools. Never invent evidence, semantic refs or analytical capability names. All requested periods are explicit in the user prompt. Do not create or publish new Recipes in this trial.'
    cmd=['claude','-p',prompt,'--output-format','stream-json','--verbose','--mcp-config',str(out/'mcp.json'),
        '--strict-mcp-config','--tools','','--allowedTools','mcp__decisionlayer',
        '--system-prompt',system,'--permission-mode','dontAsk','--max-budget-usd','4','--max-turns','40',
        '--setting-sources','','--settings','{"disableAllHooks":true,"enabledPlugins":{}}',
        '--disable-slash-commands','--effort','medium']
    (out/'protocol.json').write_text(json.dumps({'prompt':prompt,'system':system,'timeout_seconds':args.timeout,
        'budget_usd':4,'requested_model':'client configured default','data':'existing complete-journey Cube sample',
        'external_actions':'Decision Layer MCP only; no local analytical code'},indent=2)+'\n')
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='dl-claude-skill-') as cwd:
        # Stream directly to durable local logs so interrupted trials remain inspectable.
        with (out/'events.jsonl').open('wb') as stdout, (out/'stderr.log').open('wb') as stderr:
            process=await asyncio.create_subprocess_exec(*cmd,cwd=cwd,stdout=stdout,stderr=stderr)
            timed_out=False
            try:await asyncio.wait_for(process.wait(),args.timeout)
            except asyncio.TimeoutError:
                timed_out=True;process.kill();await process.wait()
    events=[]
    for line in (out/'events.jsonl').read_text().splitlines():
        try:events.append(json.loads(line))
        except json.JSONDecodeError:pass
    result=next((event for event in reversed(events) if event.get('type')=='result'),{})
    calls=[block for event in events if event.get('type')=='assistant' for block in event.get('message',{}).get('content',[]) if block.get('type')=='tool_use']
    run_ids=list(dict.fromkeys(block['input']['run_id'] for block in calls if block.get('input',{}).get('run_id')))
    records=[]
    for run_id in run_ids:
        run=call(args.api,'/runs/'+run_id)
        (out/(run_id+'.json')).write_text(json.dumps(run,ensure_ascii=False,indent=2)+'\n')
        records.append({'run_id':run_id,'status':run['status'],'active_skill_step':run.get('active_skill_step'),
            'methods':[step['step']['method'] for step in run['steps']],
            'step_statuses':[step['result']['status'] for step in run['steps']],
            'skill_query_statuses':[[q['status'] for q in step['skill']['queries']] for step in run['steps'] if step.get('skill')],
            'query_attempts':len(run['query_attempts']),
            'python_filters':run['steps'][-1]['step']['params'].get('population_filters') if run['steps'] else None})
    metrics={'exit_code':process.returncode,'timed_out':timed_out,'wall_seconds':round(time.monotonic()-started,2),
        'client_success':bool(result) and not result.get('is_error',False),'cost_usd':result.get('total_cost_usd'),
        'model_usage':result.get('modelUsage'),'tool_calls':len(calls),'tools':[c['name'] for c in calls],
        'answer':result.get('result'),'runs':records,'failure_case':args.failure_case}
    (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in metrics.items() if k not in ('answer','model_usage','tools')},ensure_ascii=False),flush=True)


if __name__=='__main__':asyncio.run(main())
