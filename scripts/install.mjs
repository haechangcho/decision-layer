#!/usr/bin/env node
// A thin installer for the existing Docker sample and stdio MCP adapter.
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { cpSync, existsSync, mkdirSync, readFileSync, writeFileSync, openSync, closeSync } from 'node:fs';
const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const root = process.env.DL_INSTALL_DIR || path.join(os.homedir(), '.local', 'share', 'decision-layer', 'runtime');
const args = process.argv.slice(2);
const command = args.shift() || 'setup';
const usage = 'Usage: decision-layer [setup|doctor|stop|replay] [--client claude|codex]';
function run(cmd, argv, options={}) {
  const r=spawnSync(cmd,argv,{cwd:root,stdio:'inherit',...options});
  if(r.error || r.status!==0) throw new Error(`${cmd} failed. ${r.error?.message || `Exit ${r.status}`}`);
  return r;
}
function available(cmd, argv) {
  const r=spawnSync(cmd,argv,{cwd:sourceRoot,stdio:'pipe'});
  return !r.error && r.status===0;
}
try {
  if(args.includes('--help') || command==='--help') { console.log(usage); process.exit(0); }
  if(args.length && (args.length!==2 || args[0]!=='--client' || !['claude','codex'].includes(args[1]))) throw new Error(usage);
  const client=args[1] || 'claude';
  const title=client==='codex' ? 'Codex' : 'Claude Code';
  const inspectArgs=['mcp','get','decision-layer-demo',...(client==='codex' ? ['--json'] : [])];
  if(!['setup','doctor','stop','replay'].includes(command)) throw new Error(usage);
  if(!available('docker',['info'])) throw new Error('Start Docker Desktop (or Docker Engine with Compose v2), then rerun.');
  if(!available('docker',['compose','version'])) throw new Error('Docker Compose v2 is required.');
  if(command==='doctor') {
    run('docker',['compose','-f','examples/quickstart/compose.yaml','ps']);
    if(!available(client,['--version'])) throw new Error(`Install ${title} first.`);
    run(client,inspectArgs);
    console.log(`Expected: healthy services and decision-layer-demo registered in ${title}.`);
  } else if(command==='stop' || command==='replay') {
    run('bash',['scripts/demo.sh',command]);
  } else {
    if(!available(client,['--version'])) throw new Error(`Install ${title} first, then rerun. For a standalone demo: bash scripts/demo.sh`);
    const bridge=path.join(root,'scripts','mcp-demo.sh');
    // Refuse to overwrite an unrelated server registered under our name.
    const existing=spawnSync(client,inspectArgs,{cwd:sourceRoot,encoding:'utf8'});
    let managed=existing.stdout?.includes(bridge);
    if(existing.status===0 && client==='codex') {
      const registered=JSON.parse(existing.stdout);
      managed=registered.transport?.command==='bash' && JSON.stringify(registered.transport?.args)===JSON.stringify([bridge]);
    }
    if(existing.error) throw new Error(`Cannot inspect ${title} MCP configuration: ${existing.error.message}`);
    if(existing.status===0 && !managed) {
      throw new Error(`decision-layer-demo already points elsewhere. Keep it, or explicitly remove it with: ${client} mcp remove decision-layer-demo`);
    }
    const marker=path.join(root,'.decision-layer-install');
    if(existsSync(root) && !existsSync(marker)) throw new Error(`Refusing to overwrite unmanaged directory: ${root}`);
    if(path.resolve(root)===sourceRoot) throw new Error('DL_INSTALL_DIR must differ from the source checkout.');
    mkdirSync(root,{recursive:true});
    const files=JSON.parse(readFileSync(path.join(sourceRoot,'package.json'),'utf8')).files;
    const excluded=/^(node_modules|\.git|\.next.*|__pycache__|results|test-results|playwright-report|\.env.*)$/;
    for(const item of [...files,'package.json']) cpSync(path.join(sourceRoot,item),path.join(root,item),{recursive:true,filter:p=>!excluded.test(path.basename(p))});
    writeFileSync(marker,'Managed by Decision Layer setup. Sample data lives in Docker volumes.\n');
    console.log('Preparing the synthetic sample and checking the saved-analysis replay. First build may take several minutes.');
    const logDir=path.join(root,'..','logs');mkdirSync(logDir,{recursive:true});
    const logPath=path.join(logDir,`setup-${Date.now()}.log`);
    const log=openSync(logPath,'w');
    try { run('bash',['scripts/demo.sh'],{stdio:['inherit',log,log]}); }
    catch(error) { throw new Error(`Setup could not finish. Details: ${logPath}\n${error.message}`); }
    finally { closeSync(log); }
    console.log(`Replay verified. Setup details: ${logPath}`);
    if(existing.status!==0) run(client,['mcp','add',...(client==='claude' ? ['--scope','user','--transport','stdio'] : []),'decision-layer-demo','--','bash',bridge]);
    console.log(`\nReady. Restart ${title}, then ask:\n\nUse Decision Layer to reuse the saved department investigation for February 2026. Show its leading department, regions and evidence.\n\nAsk for March next: tied leaders require a choice.\nNo Python install, MCP JSON or port configuration is needed. Docker must remain running.\nThis sample uses synthetic data. Connect your own semantic source separately.\nRemove the client connection: ${client} mcp remove decision-layer-demo\nInspect results: http://localhost:3100/runs\nStop the sample: rerun this installer with stop instead of setup`);
  }
} catch(error) { console.error(error.message); process.exitCode=1; }
