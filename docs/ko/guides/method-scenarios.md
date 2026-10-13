# 직접 실행하는 Method 테스트 시나리오

저장소 루트에서 실행합니다. 각 CLI는 결과를 검증하고 틀리면 nonzero exit로 종료합니다. 모든 라이브러리가 설치된 아래 환경에서는 통계 사례를 건너뛰지 않습니다.

## 1. 설치와 전체 정답 검증

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/patterns/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
.venv-method/bin/python -m examples.methods.patterns --all
.venv-method/bin/python -m examples.methods.patterns.failures --all
```

| case | 패턴 | 조회 수 | 독립 기대값 |
| --- | --- | --- | --- |
| by_group | A | 1 | 30, 20, 10 |
| trend | A | 1 | 20, 30 |
| period | B | 2 | 10 |
| peer | B | 3 | 4, 6 |
| ols | C | 1 | 2, 3 ± 0.15 |
| dowhy | C | 1 | 2 ± 0.15 |
| econml | C | 1 | 2 ± 0.15 |
| unit-change | D | 2 | 3, 5 |
| unit-change-wide | D | 2 | 3, 5 |
| did | E | 1 | 3 |
| did-split | F | 2 | 3 |
| mixed | G | 2 | 60; 10; 30; 3 |

`--all` 대신 `--case peer`처럼 하나씩 실행하세요. fixture의 전체 요청은 `scenarios.py`, 함수는 `methods.py`, 검증은 `verify()`에 있습니다. 비교 단위와 alias를 출력에서 확인할 수 있습니다. OLS는 treatment·baseline 계수, mixed는 집계·최솟값·최댓값·개체 수입니다. DoWhy/EconML의 2는 생성식에 알려진 효과이며 실제 데이터의 정답을 의미하지 않습니다.

```bash
.venv-method/bin/python -m examples.methods.patterns --case peer
.venv-method/bin/python -m pytest -q examples/methods/patterns tests/unit/test_method_authoring.py tests/unit/test_advanced_methods.py
```

## 2. 실패·거절도 확인

| case | 실제 시도 수 | 기대 결과 |
| --- | --- | --- |
| wrong-kind | 0 | InvalidBinding |
| wrong-query | 1 | AssertionError |
| no-period | 0 | Refused |
| query-budget | 1 | refused |
| provider-failure | 2 | ProviderError |
| row-overflow | 1 | refused |
| non-primary-unit | 0 | InvalidBinding |
| missing-data | 1 | refused |
| duplicate-unit | 1 | refused |
| missing-cohort | 2 | refused |
| unsupported-option | 0 | InvalidBinding |
| duplicate-panel | 1 | refused |
| overlapping-windows | 0 | refused |

잘못된 종류·기간 누락·지원하지 않는 옵션은 조회 전에 거절합니다. budget 초과는 앞선 성공 근거가 남습니다. provider 실패는 예외를 다시 발생시키며 `session.last_trial.attempts`에서 실패 label/spec을 검사합니다. 정답 검증 실패를 분석 성공으로 변환하지 않습니다.

## 3. 현재 Complete Journey 데이터로 실행

현재 데이터는 Databricks 예제를 참고해 구축한 dunnhumby Complete Journey의 PostgreSQL/Cube 샘플입니다. 실제 Databricks backend 통합 테스트는 아닙니다. 데이터를 다시 다운로드하거나 DB volume을 삭제할 필요는 없습니다. [샘플 연결](quickstart.md) 후 Cube가 **이 checkout의 최신 model**을 읽도록 서비스 설정을 확인하세요. 다른 checkout에서 이미 실행 중인 서비스는 이 코드로 자동 바뀌지 않습니다.

추가한 `campaign_panel`은 기존 eligible campaign-household의 pre/post 30일 값을 UNION ALL한 native Cube view입니다. public observation key와 panel model 갱신이 필요하며 DB 행 migration은 없습니다. 날짜는 window 시작이며 실제 처치 수령 날짜가 아닙니다.

기존 local demo의 Compose project가 `decision-layer-cube`이고 PostgreSQL을 그대로 사용할 경우, **Cube 서비스만** 최신 checkout 모델로 갱신할 수 있습니다. custom project/port이면 해당 설정을 먼저 맞추세요. 기존 API/Web는 이 명령으로 갱신되지 않습니다.

```bash
cd examples/complete-journey
docker compose -p decision-layer-cube -f compose.yaml -f compose.override.yaml up -d --no-deps cube
cd ../..
```

```bash
export DL_JOURNEY_CUBE_URL=http://127.0.0.1:4000/cubejs-api/v1
export DL_JOURNEY_DATABASE_URL='postgresql://journey_reader:local-read-only@127.0.0.1:5433/journey'
.venv-method/bin/python -m examples.methods.patterns.journey --all --verify-sql
.venv-method/bin/python -m examples.methods.patterns.journey --case did --verify-sql
.venv-method/bin/python -m examples.methods.patterns.journey --case did-split --verify-sql
.venv-method/bin/python -m examples.methods.patterns.journey --case dowhy
.venv-method/bin/python -m examples.methods.patterns.journey --case econml
```

로컬 demo reader만 위 URL을 사용합니다. 다른 환경은 해당 서버·사용자·토큰으로 바꾸세요. SQL 검증은 read-only 연결에서 실행되고 Method가 raw SQL을 실행하는 경로는 없습니다.

예상 결과: by_group·trend·period·peer·OLS·unit-change·mixed는 성공하고 독립 SQL과 일치합니다. campaign 8의 eligible observation은 2,008개입니다. OLS pre-sales 계수는 약 0.80675065, mixed 평균은 약 186.39861554입니다. 새 두 기간 대비는 연관성 차이를 반환합니다. DoWhy/EconML은 추출 후 관측 지원 범위를 검사하며 가정 체크박스를 요구하지 않습니다.

이전 Journey 실험에서 단일/분할 window 대비는 약 5.45823535로 SQL과 일치했고 campaign 8의 fitted propensity 지원 범위는 부족했습니다. 이번 리팩토링에서는 실제 연결을 재실행하지 않았습니다. 새 API도 데이터 검사를 유지하고 가정은 미검증으로 기록하며 인과성을 보장하지 않습니다.

## 4. 같은 구현을 기록되는 API에서 실행

아래는 검토된 예제 4개를 명시적으로 등록하는 개발 서버입니다. 빈 memory 저장소로 별도 port에서 실행하고 기존 서버를 덮어쓰지 않습니다. 기존 샘플은 service credential 개발 모드로만 연결합니다.

```bash
export CUBE_API_URL=http://127.0.0.1:4000/cubejs-api/v1
export CUBE_INSTANCE=journey
export CUBE_API_SECRET=local-example-secret-change-me-0123456789
export DL_ALLOW_SERVICE_CREDENTIALS=true
export DL_DATABASE_URL=memory
.venv-method/bin/python -m uvicorn examples.methods.patterns.server:create_app --factory --host 127.0.0.1 --port 8011
```

다른 터미널에서 SQL URL을 export한 뒤:

```bash
.venv-method/bin/python -m examples.methods.patterns.journey --api http://127.0.0.1:8011 --all --verify-sql
.venv-method/bin/python -m examples.methods.patterns.journey --api http://127.0.0.1:8011 --case did --verify-sql
```

`run_id`로 `GET /runs/{id}`를 조회해 canonical bindings, query attempts, 버전·검증·경고를 확인합니다. Web의 Run viewer와 MCP `run_step`도 같은 RunEngine/Registry를 사용합니다. 개발 함수 자동 업로드나 별도 실행기는 없습니다. 종료는 개발 서버 터미널에서 Ctrl-C입니다.

## 5. 수정 실험과 디버깅

`group_metric`의 order 또는 limit을 바꿔 실행하면 full-spec fixture가 불일치한 필드를 표시합니다. peer의 두 번째 호출 앞에 breakpoint를 넣으면 같은 함수에서 세 쿼리가 어떻게 이어지는지 볼 수 있습니다. `session.last_trial`의 attempts/queries/result를 검사합니다. `explore.ipynb`는 이 함수와 같은 CLI 검증 함수를 import하며 별도 구현이 없습니다.

현재 데이터는 기술통계·입력 매핑·join/grain·다중 조회·추출·실패 경로를 시험하기에 충분합니다. 인과효과 정확도에는 알려진 생성식의 합성 fixture가 필요합니다. 실제 인과 검증에는 처치 수령 시점·선정 설계·간섭/겹치는 캠페인·개체별 기간 완전성과 식별 가정을 추가로 확보해야 합니다.
