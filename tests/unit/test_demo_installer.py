"""Installer must fail safely before copying files or overwriting another MCP server."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest
import json
import sys

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.skipif(not shutil.which('node'), reason='Node is required for installer checks')
@pytest.mark.parametrize('case,expected', [
    ('docker_down', 'Start Docker'),
    ('conflict', 'already points elsewhere'),
    ('unmanaged', 'unmanaged directory'),
    ('bad_client', 'Usage:'),
])
def test_setup_preserves_existing_configuration(tmp_path, case, expected):
    tools=tmp_path/'bin';tools.mkdir()
    for name,body in {
        'docker': 'exit 1' if case=='docker_down' else 'exit 0',
        'claude': '''if [ "$1" = "--version" ]; then exit 0; fi
if [ "$2" = "get" ]; then echo 'bash /another/project/server.sh'; exit 0; fi
exit 77''' if case=='conflict' else '''if [ "$1" = "--version" ]; then exit 0; fi
exit 1''',
    }.items():
        p=tools/name;p.write_text('#!/bin/sh\n'+body+'\n');p.chmod(0o755)
    target=tmp_path/'runtime'
    if case=='unmanaged': target.mkdir();(target/'keep.txt').write_text('existing user file')
    env={**os.environ,'PATH':str(tools)+os.pathsep+os.environ['PATH'],'DL_INSTALL_DIR':str(target)}
    args=['node',str(ROOT/'scripts/install.mjs'),'setup']
    if case=='bad_client': args+=['--client','unknown']
    result=subprocess.run(args,env=env,text=True,capture_output=True,timeout=10)
    assert result.returncode!=0
    assert expected in result.stderr
    if case=='unmanaged': assert (target/'keep.txt').read_text()=='existing user file'
    else: assert not target.exists()


@pytest.mark.skipif(not shutil.which('node'), reason='Node is required for installer checks')
@pytest.mark.parametrize('client', ['claude', 'codex'])
def test_setup_registers_selected_client_and_is_idempotent(tmp_path, client):
    # A minimal distribution and stub executables exercise copying, command
    # construction and reinstallation without changing the user's MCP config.
    source = tmp_path / 'source'
    (source / 'scripts').mkdir(parents=True)
    shutil.copy(ROOT / 'scripts/install.mjs', source / 'scripts/install.mjs')
    (source / 'scripts/mcp-demo.sh').write_text('#!/bin/sh\n')
    (source / 'package.json').write_text(json.dumps({'files': ['scripts']}))
    target = tmp_path / 'runtime with spaces'
    tools = tmp_path / 'bin'
    tools.mkdir()
    log = tmp_path / 'commands.jsonl'
    for name in ('docker', 'bash', client):
        executable = tools / name
        executable.write_text(f'#!{sys.executable}\n' + '''
import json, os, pathlib, sys
with open(os.environ['TEST_COMMANDS'], 'a') as out:
    out.write(json.dumps([pathlib.Path(sys.argv[0]).name, *sys.argv[1:]]) + '\\n')
if sys.argv[1:3] == ['mcp', 'get']:
    if not os.environ.get('TEST_REGISTERED'):
        sys.exit(1)
    bridge = str(pathlib.Path(os.environ['DL_INSTALL_DIR']) / 'scripts/mcp-demo.sh')
    if pathlib.Path(sys.argv[0]).name == 'codex':
        print(json.dumps({'transport': {'command': 'bash', 'args': [bridge]}}))
    else:
        print('Command: bash ' + bridge)
''')
        executable.chmod(0o755)
    env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH'],
           'DL_INSTALL_DIR': str(target), 'TEST_COMMANDS': str(log)}
    command = [shutil.which('node'), str(source / 'scripts/install.mjs'), 'setup', '--client', client]
    first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=15)
    assert first.returncode == 0, first.stderr
    second = subprocess.run(command, env={**env, 'TEST_REGISTERED': '1'}, capture_output=True, text=True, timeout=15)
    assert second.returncode == 0, second.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    registrations = [call for call in calls if call[:3] == [client, 'mcp', 'add']]
    expected = [client, 'mcp', 'add', *(['--scope', 'user', '--transport', 'stdio'] if client == 'claude' else []),
                'decision-layer-demo', '--', 'bash', str(target / 'scripts/mcp-demo.sh')]
    assert registrations == [expected]
    assert (target / '.decision-layer-install').exists()
