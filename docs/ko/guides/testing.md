---
title: 테스트
description: 단위 테스트부터 웹과 실제 MCP 실행까지 검증합니다.
---

# 테스트

[개발 의존성](development.md)을 설치한 뒤 변경한 부분에 맞는 작은 테스트부터 실행하세요. 실제 연동 테스트는 Run과 Recipe 후보를 만들므로 독립된 샘플 환경을 사용합니다.

## 단위 테스트와 API 계약

저장소 루트에서 실행합니다.

```bash
.venv/bin/pytest
.venv/bin/pytest tests/unit/test_methods.py
```

실행 중인 데이터 소스는 필요하지 않습니다. 실제 연동 테스트는 전용 환경변수를 설정하지 않으면 건너뜁니다. 건너뛴 테스트는 연동을 검증한 것이 아닙니다. `tests/fixtures/`의 합성 메타데이터는 계약 검증용이며 별도 배포 예제가 아닙니다.

## 웹 테스트

`web/`에서 실행합니다.

```bash
npm run typecheck
npm run build
npx playwright install chromium
```

한 터미널에서 `npm run dev`로 웹을 실행한 뒤 다른 터미널의 `web/`에서 테스트합니다.

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

기본 제품 테스트는 API 응답을 모의해 데스크톱·모바일의 화면 상태와 조작을 확인합니다. 실제 소스는 필요하지 않습니다. 실제 연동 시나리오는 해당 환경변수가 없으면 건너뜁니다. 실패 화면과 trace는 `web/test-results/`에 저장됩니다.

## Complete Journey 실제 연동

[기본 샘플](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)을 Recipe가 비어 있는 독립 환경에서 시작하세요. 예제 폴더에서 데이터 적재를 확인합니다.

```bash
docker compose -p decision-layer-cube run --rm --no-deps import python verify.py
```

저장소 루트에서 MCP와 실행 엔진을 검증합니다.

```bash
DL_JOURNEY_API_URL=http://127.0.0.1:8000 \
  .venv/bin/pytest -q -s tests/provider/test_complete_journey_live.py
.venv/bin/pytest examples/method-template/test_method.py
```

실제 연동 테스트는 Recipe 없이 MCP로 드릴다운·동료 집단 비교를 실행하고 Recipe 후보를 검토합니다. Method 템플릿 테스트는 실제 소스 없이 실행됩니다.

dbt 예제에서도 같은 MCP 테스트를 `DL_JOURNEY_PROVIDER=metricflow`로 실행할 수 있습니다. 같은 DB로 두 엔진의 결과를 비교하려면 `docker compose -p decision-layer-cube -f compose.yaml -f compose.override.yaml -f compose.dbt.yaml up -d --build --wait cube metricflow`로 두 소스만 실행하고, 저장소 루트에서 `DL_METRICFLOW_TEST_URL=http://127.0.0.1:4100 .venv/bin/pytest tests/provider/test_metricflow_live.py -q`를 실행하세요. 네 Method와 캠페인·접촉·쿠폰 사용 이력의 조인·기간 필터를 비교하며 Run은 만들지 않습니다.

출력된 `JOURNEY_MCP_RUN_ID`를 사용해 `web/`에서 화면을 확인합니다.

```bash
JOURNEY_RUN_ID=run_replace_with_printed_id PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 \
  npm run test:e2e -- tests/product/complete-journey-live.spec.ts
```

실제 API·웹 포트에 맞게 바꾸세요. 테스트를 맞추려고 개인 Recipe를 삭제하지 말고 별도 샘플 폴더를 사용하세요. 브라우저 테스트는 저장 전 후보를 검토하며 Recipe를 게시하지 않습니다.

## dbt 공식 API 검증

`tests/unit/test_dbt_provider.py`는 공식 GraphQL 계약을 모의 응답으로 검사합니다. Method 실행과 Run을 Recipe로 전환하는 과정도 포함합니다. 실제 공식 API는 별도의 조회 전용 테스트로 확인합니다.

```bash
# 비공개 환경 설정에 다음 값을 준비하세요.
# DL_DBT_TEST_URL, DL_DBT_TEST_ENVIRONMENT_ID,
# DL_DBT_TEST_TOKEN, DL_DBT_TEST_METRIC (해당 환경의 지표 이름)
.venv/bin/pytest tests/provider/test_dbt_live.py -q
```

값이 없으면 테스트를 건너뜁니다. 로컬 dbt 예제의 성공은 공식 API 인증이나 실제 웨어하우스 동작을 검증한 것이 아닙니다.

## 결과 해석

| 검증 | 확인하는 것 | 확인하지 않는 것 |
| --- | --- | --- |
| 단위·모의 API 테스트 | 계약과 알려진 동작 | 실제 소스 호환성 |
| 모의 브라우저 테스트 | 화면 상태와 조작 | 실제 쿼리·AI의 계획 |
| 독립 SQL 기준값·실제 MCP | 적재 정확성과 명시한 도구 실행 | 자연어에 따른 도구 선택 |
| 실제 AI 클라이언트 실행 | 특정 질문에서 해당 클라이언트의 행동 | 일반적인 정확도 향상·인과 정확성 |

[AI 클라이언트](mcp.md)에서 직접 질문하는 과정도 별도로 확인하세요. 클라이언트·모델, 질문, Run ID, 사용 Method, 경고, 기준값 비교를 기록합니다. 제품 간 비교나 성능 주장은 [분석 품질 평가](evaluation.md)를 따르세요.

CI는 Python 계약과 Method 템플릿, 웹 타입 검사·빌드, 문서 빌드, Docker 온보딩, Complete Journey SQL·MCP 실행을 검사합니다. 위 브라우저 테스트는 직접 수행하는 검사이며 CI에서 자동 실행된다고 가정하면 안 됩니다. 샘플 검증 작업은 원본 데이터 제공처에 접근할 수 있어야 합니다.
