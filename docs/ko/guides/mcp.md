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

한 질문의 분석은 하나의 Run에서 진행합니다. Recipe가 없으면 `start_analysis`, 맞는 Recipe가 있으면 `start_run`으로 시작합니다. 모든 Method는 같은 Run ID에 `run_step`으로 추가하며, 각 단계의 목적을 반드시 입력합니다. 독립 Run을 만드는 `run_method` MCP 도구는 제공하지 않습니다.

서버는 빈 질문, 목적 없는 단계, 실행 단계에 근거가 연결되지 않은 결론을 거절합니다. Method나 pipeline 실행이 끝나도 `complete_run`으로 결론을 저장해야 분석이 완료됩니다. AI가 결론 저장을 빠뜨리면 웹에 **결론 대기**로 남습니다. 사용자가 결과를 검토하고 결론을 저장하면 전체 절차를 Recipe로 등록할 수 있습니다. 업데이트 후에는 MCP 클라이언트를 재시작해 변경된 도구 목록을 불러오세요.

## 다음 분석에서도 선택 규칙 유지하기

일반 드릴다운은 `step_id`와 `selection_sources`를 반환합니다. 순위 1위 그룹을 따라 내려갈 때는 이름을 복사하지 말고 반환된 `path` 참조를 다음 단계의 `drill_path`에 넣습니다. 최고 구성원의 동료 비교는 `condition` 참조를 `subject`, `parents` 참조를 `peers`에 넣습니다. 엔진이 규칙과 적용값을 함께 기록하며, 일부만 조회된 결과는 자동 선택하지 않습니다. 동률이면 입력을 요청합니다.

Run에서는 특정 대상을 직접 지정할 수 있지만, **Recipe로 등록**은 팝업 없이 runtime 선택 규칙이나 필수 실행 입력으로 저장합니다. 이전 결과값을 기본 대상에 고정하지 않습니다. Recipe의 명시적인 고정 정책은 유지합니다. 선언된 실행 입력은 `list_recipes`에서 확인하고 `start_run`의 `inputs`로 전달합니다. [Recipe 만들기](recipes.md)에서 더 자세히 확인할 수 있습니다.

## 질문하고 확인하기

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 원래 질문과 단계별 목적을 Run에 남기고 Run ID를 알려줘.

클라이언트는 적절한 Recipe가 있으면 이를 사용하고, 없으면 등록된 Method와 semantic catalog를 바탕으로 탐색할 수 있습니다. 완료 후 [Runs](http://localhost:3000/runs)에서 질문, 방법, 설정, 쿼리와 출처를 검토하세요. 좋은 절차라면 [Recipe로 등록](./runs.md)할 수 있습니다.

로컬 Cube·dbt 예제는 개발용 서비스 계정을 사용하므로 별도 토큰이 필요 없습니다. 회사의 기존 소스에 연결할 때는 MCP 클라이언트의 비공개 환경 설정에 `DL_TOKEN`을 지정하세요. 웹과 MCP에서 같은 연결과 인증 정보를 사용해야 같은 Runs를 볼 수 있습니다. [Cube 연결](cube.md)과 [dbt Semantic Layer 연결](dbt.md)을 참고하세요.

Claude Desktop 설정과 오류별 확인 방법은 [영문 MCP 가이드](/guides/mcp)에 있습니다.
