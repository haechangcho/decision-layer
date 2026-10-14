"""Installer must fail safely before copying files or overwriting another MCP server."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

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
