---
title: AI 도구 연결
description: Claude 또는 Codex에서 등록된 분석 기능과 Recipe를 사용합니다.
---

# AI 도구 연결

MCP 어댑터는 내 컴퓨터에서 stdio로 실행되고 Decision Layer API에 요청합니다. AI 모델의 인증 정보는 Claude나 Codex가 관리합니다. 먼저 [예제](../index.md) 또는 API와 Cube를 실행해 두세요.

## 설치

저장소 루트에서 Python 3.11 이상을 사용하세요.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
```

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://localhost:8000 -- "$(pwd)/.venv/bin/decision-layer-mcp"
codex mcp list
```

새 세션에서 `/mcp`로 연결을 확인하세요.

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://localhost:8000 --transport stdio decision-layer -- "$(pwd)/.venv/bin/decision-layer-mcp"
claude mcp list
```

새 세션에서 `/mcp`로 연결을 확인하세요. 다른 MCP 클라이언트는 같은 실행 파일과 `DL_API_URL`을 stdio 서버로 설정하면 됩니다.

## 질문하고 확인하기

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 원래 질문과 단계별 목적을 Run에 남기고 Run ID를 알려줘.

클라이언트는 적절한 Recipe가 있으면 이를 사용하고, 없으면 등록된 Method와 semantic catalog를 바탕으로 탐색할 수 있습니다. 완료 후 [Runs](http://localhost:3000/runs)에서 질문, 방법, 설정, 쿼리와 출처를 검토하세요. 좋은 절차라면 [Recipe로 등록](./runs.md)할 수 있습니다.

예제에서는 로컬 개발용 서비스 계정을 쓰므로 별도 토큰이 필요 없습니다. 사용자별 Cube 인증을 쓰는 환경에서는 어댑터에 `DL_TOKEN`을 전달하고 웹에서도 같은 사용자로 접속해야 자신의 Runs가 보입니다.

Claude Desktop 설정과 오류별 확인 방법은 [영문 MCP 가이드](/guides/mcp)에 있습니다.
