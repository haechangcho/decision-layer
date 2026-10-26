# AI 도구 연결

[Decision Layer 서버](quickstart.md)를 켜 두고, 새 터미널에서 설치에 사용한 가상환경을 활성화하세요.
사용하는 AI 도구 하나를 선택해 연결합니다.

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui -- "$(command -v decision-layer-mcp)"
codex mcp list
```

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui --transport stdio decision-layer -- "$(command -v decision-layer-mcp)"
claude mcp list
```

## Claude Desktop

**Settings → Developer → Edit Config**에서 설정 파일을 엽니다.
먼저 실행 파일 경로를 확인하세요.

```bash
which decision-layer-mcp
```

아래 `command`를 출력된 경로로 바꾸고, 기존 `mcpServers`에 추가합니다.

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

저장 후 앱을 완전히 종료하고 다시 엽니다.

## 질문하기

먼저 연결을 확인합니다.

> 사용할 수 있는 지표와 분석 방법을 보여줘.

샘플 서버에서는 다음처럼 요청해 보세요.

> 샘플의 2001년 2월 매출이 가장 큰 상품 부문과 해당 부문의 매장별 매출을 알려줘.

AI가 Method와 데이터를 선택하고, Decision Layer가 조회와 계산을 수행합니다.
답변의 Run 링크에서 결과와 쿼리를 확인하세요.
호출과 응답은 [Python Method 만들기](../tutorials/write-your-method.md)에서 살펴볼 수 있습니다.

## 연결 설정

서버 포트를 바꿨다면 `DL_API_URL`과 `DL_WEB_URL`도 맞추세요.

| 환경변수 | 용도 |
|---|---|
| `DL_API_URL` | API 주소 |
| `DL_WEB_URL` | 결과 링크에 사용할 관리자 화면 주소 |
| `DL_TOKEN` | Cube 사용자 인증 토큰 |
| `DL_LOCALE` | 메시지 언어. 한국어는 `ko` |

## 연결되지 않을 때

- **`ENOENT`**: 가상환경을 활성화하고 `which decision-layer-mcp`로 경로를 확인합니다. Claude Code의 잘못된 등록은 `claude mcp remove --scope user decision-layer`로 삭제한 뒤 다시 연결하세요.
- **API 연결 실패**: 서버 실행 상태와 포트를 확인합니다.
- **권한 오류**: [Cube 연결](cube.md)의 인증 설정을 확인합니다.
- **도구가 보이지 않음**: AI 클라이언트를 다시 시작합니다.
