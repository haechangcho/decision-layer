from fastapi.testclient import TestClient

from decision_layer.cli import init_project, new_method
from decision_layer.console import create_console
from decision_layer.settings import Settings


def test_console_shares_project_and_api_preserving_existing_routes(tmp_path):
    project = init_project(tmp_path / 'team')
    new_method(project, 'python', 'rank')
    ui = tmp_path / 'ui'
    (ui / 'assets').mkdir(parents=True)
    (ui / 'index.html').write_text('<html>console</html>')
    (ui / 'assets' / 'app.js').write_text('/* bundle */')
    app = create_console(Settings(project_dir=str(project.root), database_url='memory'), ui)
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get('/').text == '<html>console</html>'
        assert client.get('/ui/methods/team.rank').text == '<html>console</html>'
        assert client.get('/ui/assets/app.js').status_code == 200
        assert client.get('/ui/assets/missing.js').status_code == 404
        direct = client.get('/methods/team.rank')
        proxied = client.get('/api/methods/team.rank')
        assert direct.status_code == proxied.status_code == 200
        assert direct.json() == proxied.json()
        assert client.get('/api/project').json()['name'] == 'team'
        assert client.get('/api/missing').status_code == 404
        assert client.get('/api/project', headers={'Host': 'evil.example'}).status_code == 403
