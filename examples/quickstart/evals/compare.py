"""Paired live-model pilot: semantic MCP + instructions vs Decision Layer + saved Recipe.
No aggregate performance claim should be made from this tiny public fixture.
"""
import argparse
import asyncio
import datetime
import json
import os
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import random
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
PROCEDURE = '''You are an analytics assistant. Use only the supplied MCP tools. Discover the governed revenue metric and date/department/region dimensions. For the requested month, query revenue by department across the entire month, check all eligible groups, select the unique highest-revenue department, then break that department's revenue down by region. Never reuse a previous winner without checking the new period. If leaders tie, ask which to inspect instead of selecting one or querying a regional branch. Report the leading department and its amount, each region and amount, and relevant limits. This is synthetic data and descriptive ranking, not causal evidence. If a saved executable procedure matches these instructions, use it. Record evidence using the tools available to you. Do not invent data or silently change periods.'''
CASES = [('january','January 2026', 'Home',6200,3720,2480),
         ('february','February 2026','Grocery',6720,4032,2688),
         ('march','March 2026',None,3720,None,None)]

def usage_totals(result):
    models=result.get('modelUsage') or {}
    fields=('inputTokens','outputTokens','cacheReadInputTokens','cacheCreationInputTokens')
    totals={k:sum(v.get(k,0) for v in models.values()) for k in fields}
    totals['total_tokens']=sum(totals.values())
    return totals

async def trial(condition, case, repeat, config, output, model):
    key, month, leader, amount, north, south = case
    prompt=f'Investigate revenue for {month} using the supplied procedure.'
    cmd=['claude','-p',prompt,'--output-format','stream-json','--verbose','--mcp-config',str(config),
         '--strict-mcp-config','--tools','','--allowedTools','mcp__benchmark','--system-prompt',PROCEDURE,
         '--permission-mode','dontAsk','--max-budget-usd','2','--max-turns','20',
         '--setting-sources','','--settings','{"disableAllHooks":true,"enabledPlugins":{}}',
         '--disable-slash-commands','--effort','medium']
    if model: cmd.extend(['--model',model])
    started=time.monotonic()
    with tempfile.TemporaryDirectory() as cwd:
        p=await asyncio.create_subprocess_exec(*cmd,cwd=cwd,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try: raw,err=await asyncio.wait_for(p.communicate(),300)
        except asyncio.TimeoutError:
            p.kill();raw,err=await p.communicate()
            err+=b'\nTIMEOUT 300s'
    elapsed=time.monotonic()-started
    events=[json.loads(s) for s in raw.decode().splitlines() if s.startswith('{')]
    (output/f'{key}-{repeat}-{condition}.json').write_text(json.dumps(events,ensure_ascii=False,indent=2)+'\n')
    result=next((e for e in reversed(events) if e.get('type')=='result'),{})
    calls=[c for e in events if e.get('type')=='assistant' for c in e.get('message',{}).get('content',[]) if c.get('type')=='tool_use']
    answer=result.get('result','')
    normalized=answer.replace(',','')
    # Screening only. Review complete transcripts for selection, period and causal claims.
    expected=([leader,str(amount),'North',str(north),'South',str(south)] if leader else ['Home','Grocery',str(amount)])
    numeric_screen=all(x.lower() in normalized.lower() for x in expected)
    row={'condition':condition,'case':key,'repeat':repeat,'wall_seconds':round(elapsed,2),
         'cost_usd':result.get('total_cost_usd'),'models':list((result.get('modelUsage') or {}).keys()),
         **usage_totals(result),'tool_calls':len(calls),'completed':p.returncode==0 and bool(result) and not result.get('is_error',False),
         'numeric_screen':numeric_screen,'answer':answer,'stderr':err.decode()[-600:],'exit_code':p.returncode,'timeout':'TIMEOUT 300s' in err.decode()}
    (output/f'{key}-{repeat}-{condition}-metrics.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in row.items() if k not in ('answer','stderr') }),flush=True)
    return row

async def preflight(server, expected):
    params=StdioServerParameters(command=server['command'],args=server.get('args',[]),env={**os.environ,**server.get('env',{})})
    async with stdio_client(params) as (r,w):
        async with ClientSession(r,w) as session:
            await session.initialize()
            names={t.name for t in (await session.list_tools()).tools}
            if not expected <= names: raise RuntimeError(f'Missing tools: {expected-names}')
            if 'get_catalog' in names:
                result=await session.call_tool('get_catalog',{})
                if result.is_error: raise RuntimeError(str(result.content))
    print('Preflight OK:',sorted(expected),flush=True)

async def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeats',type=int,default=3)
    ap.add_argument('--model',default=None)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.repeats<1: ap.error('--repeats must be positive')
    output=(args.output or Path(__file__).parent/'results'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S-comparison')).resolve()
    output.mkdir(parents=True,exist_ok=True)
    configs={
      'semantic': {'command':str(ROOT/'.venv/bin/python'),'args':[str(Path(__file__).with_name('cube_mcp.py'))],'env':{'BENCH_CUBE_URL':os.environ.get('BENCH_CUBE_URL','http://127.0.0.1:4100/cubejs-api/v1')}},
      'recipe': {'command':str(ROOT/'.venv/bin/decision-layer-mcp'),'env':{'DL_API_URL':os.environ.get('DL_API_URL','http://127.0.0.1:8100'),'DL_WEB_URL':'http://localhost:3100'}}}
    for condition,server in configs.items():
        await asyncio.wait_for(preflight(server, {'get_catalog','query_metrics'} if condition=='semantic' else {'find_recipes','start_run'}),45)
        (output/f'{condition}-mcp.json').write_text(json.dumps({'mcpServers':{'benchmark':server}}))
    (output/'protocol.json').write_text(json.dumps({'procedure':PROCEDURE,'cases':CASES,'repeats':args.repeats,
       'script_version':'1.0','seed':42,'effort':'medium','personal_settings_and_skills':'disabled','requested_model':args.model,'budget_usd_per_trial':2,'max_turns':20,'timeout_seconds':300,
       'note':'Steady-state reuse; excludes recipe authoring, installation and infrastructure costs. Public synthetic cases; numeric screening needs manual review.'},indent=2))
    randomizer=random.Random(42);rows=[]
    # Sequential trials avoid contention; randomize condition order within each pair.
    for repeat in range(args.repeats):
        cases=list(CASES);randomizer.shuffle(cases)
        for case in cases:
            order=list(configs);randomizer.shuffle(order)
            for condition in order:
                rows.append(await trial(condition,case,repeat,output/f'{condition}-mcp.json',output,args.model))
                (output/'metrics.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print(f'Results: {output}',flush=True)

if __name__=='__main__': asyncio.run(main())
