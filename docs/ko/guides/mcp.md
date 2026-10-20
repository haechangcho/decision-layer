# AI 도구 연결

AI가 등록된 Method와 Recipe를 찾고 실행하도록 MCP를 연결합니다. 먼저 [Decision Layer 서버](quickstart.md)를 실행해 두세요.

MCP 어댑터는 내 컴퓨터에서 실행되고 Decision Layer API에 요청합니다. 로컬 stdio를 지원하는 클라이언트에서 사용할 수 있습니다.

서버를 실행한 터미널은 켜두세요. 아래 설치와 연결 명령은 새 터미널에서 같은 가상환경을 활성화한 뒤 실행합니다.

## 어댑터 설치

Decision Layer를 설치한 가상환경에서 실행합니다.

```bash
pip install --pre 'decision-layer[mcp]'
```

아래 연결 명령은 설치된 실행 파일의 경로를 자동으로 사용합니다. 서버의 포트를 바꿨다면 API와 Web 주소도 맞춥니다.

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui -- "$(command -v decision-layer-mcp)"
codex mcp list
```

[Codex MCP](https://developers.openai.com/codex/mcp)

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui --transport stdio decision-layer -- "$(command -v decision-layer-mcp)"
claude mcp list
```

[Claude Code MCP](https://code.claude.com/docs/en/mcp)

## Claude Desktop

앱의 **Settings → Developer → Edit Config**에서 설정 파일을 엽니다. macOS에서는 다음 위치에 있습니다.

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

먼저 실행 파일의 경로를 확인합니다.

```bash
which decision-layer-mcp
```

아래 JSON의 `command`를 출력된 경로로 바꾸고, 기존 `mcpServers` 항목을 유지하면서 `decision-layer`를 추가합니다.

```json
{
  "mcpServers": {
    "decision-layer": {
      "command": "/absolute/path/decision-layer-mcp",
      "env": {
        "DL_API_URL": "http://127.0.0.1:8000",
        "DL_WEB_URL": "http://127.0.0.1:8000/ui"
      }
    }
  }
}
```

저장한 뒤 Claude Desktop을 완전히 종료하고 다시 엽니다. 자세한 설정은 [공식 로컬 MCP 가이드](https://modelcontextprotocol.io/docs/develop/connect-local-servers)를 참고하세요.

## 질문하고 결과 확인하기

먼저 “사용할 수 있는 지표와 분석 방법을 보여줘”라고 질문해 연결을 확인합니다. 샘플 서버에서는 이어서 다음 질문을 할 수 있습니다.

> 2026년 2월 매출 1위 부문과 해당 부문의 지역별 매출을 알려줘. 사용한 지표와 분석 근거도 보여줘.

AI는 등록된 분석 방법과 semantic catalog를 확인하고, 필요한 입력을 선택합니다. 의미나 기간이 모호하면 사용자에게 묻습니다.

분석 후 반환한 Run 링크에서 결과와 쿼리를 확인할 수 있습니다. 반복할 분석이라면 [Recipe로 저장](recipes.md)해 재사용합니다.

## 연결 설정

| 환경변수 | 용도 |
|---|---|
| `DL_API_URL` | Decision Layer API 주소 |
| `DL_WEB_URL` | 결과 링크에 사용할 관리자 화면 주소 |
| `DL_TOKEN` | 기존 Cube 사용자에게 필요한 bearer token |
| `DL_LOCALE` | Method 메시지 언어. 한국어는 `ko` |

샘플에는 2026년 1월부터 3월까지의 매출, 부문, 지역 데이터가 있습니다. 위 질문의 2월 매출 1위는 Grocery이고 매출은 6,720입니다.

샘플 서버는 로컬 테스트용 인증을 사용합니다. 실제 연결의 토큰은 클라이언트의 비공개 설정에 보관하고 Git에 올리지 않습니다.

## 연결되지 않을 때

- **`ENOENT` 또는 실행 파일을 찾지 못함**: 설치한 가상환경을 활성화하고 `which decision-layer-mcp`로 경로를 확인합니다. Claude Code에 잘못 등록했다면 `claude mcp remove --scope user decision-layer`로 삭제한 뒤 위 연결 명령을 다시 실행합니다.
- **API에 연결되지 않음**: 서버 실행 상태와 `DL_API_URL`의 포트를 확인합니다.
- **권한 오류나 지표 누락**: [Cube 연결](cube.md)의 토큰과 접근 권한을 확인합니다.
- **도구가 보이지 않음**: 클라이언트나 MCP 세션을 다시 시작합니다.

어댑터를 터미널에서 직접 실행하면 입력을 기다릴 수 있습니다. 실제 요청은 MCP 클라이언트가 전달합니다.
