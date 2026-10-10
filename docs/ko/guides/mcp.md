---
title: AI 도구 연결
description: Claude 또는 Codex에서 등록된 분석 기능과 Recipe를 사용합니다.
---

# AI 도구 연결

MCP 어댑터는 내 컴퓨터에서 stdio로 실행되고 Decision Layer API에 요청합니다. AI 모델의 인증 정보는 Claude나 Codex가 관리합니다. 먼저 [예제](../index.md) 또는 API와 Cube를 실행해 두세요.

사용자는 비즈니스 질문만 하면 됩니다. Run 생성이나 ID를 따로 요청할 필요는 없습니다.
분석할 수 없으면 AI가 `report_analysis_blocked`로 질문, 중단 이유와 보완 제안을
기록하고 링크를 답변에 제공합니다. 기록은 모델 수정이나 제안 승인을 뜻하지 않습니다.
웹 주소가 `http://localhost:3000`이 아니라면 MCP 환경변수 `DL_WEB_URL`을 설정하세요.
도구 변경 후에는 MCP 연결을 다시 시작해야 합니다. AI가 도구를 호출하지 않고
대화에서만 답한 내용까지 서버가 자동으로 수집하는 것은 아닙니다.

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

## Recipe 선택과 질문별 해결 상태

업데이트 후 MCP 클라이언트를 다시 시작하세요. `start_analysis`와 `start_run`은
`goals`, `run_step`은 `goal_ids`를 받습니다. 이전 실행 기록은 그대로 읽을 수 있습니다.

1. 필요한 지표와 차원을 찾고 Method의 `provides`를 확인합니다.
2. 원래 질문과 요구사항을 `find_recipes`에 전달합니다. 후보의 적용 질문, 해결할
   부분, 충돌과 필요한 입력을 확인합니다. 후보가 없으면 조회나 Method로 진행합니다.
   후보 순위는 질문에 적합하다는 증명이 아닙니다.
3. 질문 하나에 Run 하나를 시작합니다. 답해야 할 부분마다 `id`, `description`,
   `semantic_refs`, `required_capabilities`, `interpretation`을 기록합니다. Recipe를
   선택했다면 `recipe_selection`에 선택 이유와 해결할 `goal_ids`를 남깁니다.
4. 단순 지표 조회는 `query.aggregate`, 분석 계산은 등록된 Method를 사용합니다.
   각 단계에 목적과 `goal_ids`를 지정합니다. 기간 생략은 전체 기간이 아닙니다.
5. 완료할 때 요구사항별 `goal_outcome`을 남깁니다. 해결한 부분에는 근거 단계,
   해결하지 못한 부분에는 이유를 기록합니다. 조회만으로 인과 효과를 주장할 수 없습니다.

탐색 중 같은 Run에 `use_recipe`로 pipeline Recipe 하나를 적용할 수 있습니다.
성공 후 추가 단계는 `exploration=true`로 실행합니다. Recipe의 지표, 설정, 공통
조건과 조회 한도는 그대로 적용됩니다. 여러 Recipe나 중첩 실행은 지원하지 않습니다.

Method가 없어 해결하지 못했다면 사용자에게 기여 의사를 확인합니다.
`prepare_method_proposal`은 사용자가 명시한 공개 문장으로 GitHub 초안과 기존 이슈
검색 링크를 만듭니다. 실행 데이터와 쿼리를 복사하지 않으며, GitHub에서 검토하고
등록해야 이슈가 만들어집니다. 등록되지 않은 분석 코드를 대신 실행하지 않습니다.

## 다른 기간으로 Recipe 재사용

후보의 `source_question`은 처음 분석한 질문입니다. 적용 설명인 `objective`와 실제
절차인 `reuse.procedure`를 구분합니다. 원래 질문에 상반기라고 적혀 있어도 다음
실행의 기간을 고정하지 않습니다. 실제 고정 조건은 `reuse.required_filters`,
고정 비교 기간은 `reuse.period.fixed_method_periods`에서 확인합니다.

적합한 후보가 있다면 새 기간과 `recipe_selection`을 전달해 실행합니다.
후보를 사용하지 않는다면 `start_analysis`의 `recipe_review`에 Recipe 참조,
`decision: skipped`, 구체적인 `reason`을 기록합니다. 서버는 현재 후보를 재확인하고
Run에 판단 당시 후보와 이유를 저장합니다. 이유의 사실성을 자동 검증하지는 않습니다.
이전 Run의 누락된 판단 이유를 추정해 채우지 않습니다. 업데이트 후 MCP를 재시작하세요.

## 분석 질문

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 원래 질문과 단계별 목적을 Run에 남기고 Run ID를 알려줘.

클라이언트는 적절한 Recipe가 있으면 이를 사용하고, 없으면 등록된 Method와 semantic catalog를 바탕으로 탐색할 수 있습니다. 완료 후 [Runs](http://localhost:3000/runs)에서 질문, 방법, 설정, 쿼리와 출처를 검토하세요. 좋은 절차라면 [Recipe로 등록](./runs.md)할 수 있습니다.

로컬 Cube 예제는 개발용 서비스 계정을 사용하므로 별도 토큰이 필요 없습니다. 회사의 기존 소스에 연결할 때는 MCP 클라이언트의 비공개 환경 설정에 `DL_TOKEN`을 지정하세요. 웹과 MCP에서 같은 연결과 인증 정보를 사용해야 같은 Runs를 볼 수 있습니다. [Cube 연결](cube.md)과 [dbt Semantic Layer 연결](dbt.md)을 참고하세요.

Claude Desktop 설정과 오류별 확인 방법은 [영문 MCP 가이드](/guides/mcp)에 있습니다.
