"""Check the installed distribution without importing from the source checkout."""

import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import decision_layer


assert Path(decision_layer.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
print('Installed:', importlib.metadata.version('decision-layer'), decision_layer.__file__)
cli = Path(sys.executable).parent / 'decision-layer'


def run(*args, cwd):
    return subprocess.check_output([str(cli), *args], cwd=cwd, text=True)


with tempfile.TemporaryDirectory(prefix='decision-layer-install-') as folder:
    root = Path(folder)
    run('init', 'qa_team', cwd=root)
    project = root / 'qa_team'
    run('new', 'python', 'rank', cwd=project)
    run('new', 'skill', 'review', cwd=project)
    print(run('check', cwd=project))
    methods = json.loads(run('list', '--json', cwd=project))
    assert {'qa_team.rank', 'qa_team.review'} <= {item['name'] for item in methods}
    subprocess.run(
        [sys.executable, '-c', '''
import pandas as pd
from qa_team.methods.rank.method import analyze
from decision_layer.console import create_console
from decision_layer.settings import Settings
from fastapi.testclient import TestClient
from pathlib import Path
result = analyze(pd.DataFrame({'group': ['A', 'B', 'C'], 'value': [30, 20, 20]}))
assert result['rank'].tolist() == [1.0, 2.0, 2.0]
with TestClient(create_console(Settings(project_dir=str(Path.cwd()), database_url='memory')), base_url='http://localhost') as client:
    assert client.get('/ui/methods/qa_team.rank').status_code == 200
    assert 'text/html' in client.get('/ui/').headers['content-type']
    response = client.get('/api/methods/qa_team.rank')
    assert response.status_code == 200, response.text
print('Installed CLI, calculation and API discovery passed')
'''],
        cwd=project,
        check=True,
    )
