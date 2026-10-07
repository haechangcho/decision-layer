# 로컬 dbt 예제

회사의 기존 dbt 플랫폼은 [dbt Semantic Layer](dbt.md)로 연결하세요. 이 문서는 계정 없이 실행하는 로컬 예제와 개발 환경을 설명합니다.

직접 운영하는 dbt MetricFlow를 HTTP 게이트웨이로 연결할 수 있습니다. 지표 정의와 조인은 dbt가 관리하고, 쿼리 생성과 실행은 MetricFlow가 담당합니다. Decision Layer의 Method·Recipe·Run·MCP 실행 방식은 그대로 사용합니다.

현재 로컬 예제에서 검증한 조합은 **dbt Core + MetricFlow + PostgreSQL**입니다. 회사의 dbt 환경에는 [공식 Semantic Layer API](dbt.md)로 연결하세요.

## 예제로 시작하기

저장소 루트에서 실행합니다.

```bash
cd examples/complete-journey
docker compose -p decision-layer-dbt -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

PostgreSQL·dbt 초기화 작업·MetricFlow·API·웹이 실행됩니다. Cube 예제는 같은 원본 데이터를 사용하는 별도 선택지입니다. dbt 초기화 작업은 `journey_dbt` 스키마에 뷰를 만들며 원본 데이터를 복제하거나 다시 적재하지 않습니다. 처음 설치하면 MetricFlow가 자동 선택됩니다.

1. [연결 설정](http://localhost:3000/sources)을 엽니다.
2. **dbt MetricFlow**를 선택합니다. 예제의 주소 `http://metricflow:4100`, 연결 이름 `journey`, 로컬 인증 설정이 채워집니다.
3. **연결 테스트** 후 **설정 저장**을 누릅니다.
4. 지표 화면을 열거나 MCP에 연결한 AI에게 현재 카탈로그를 확인하고 분석하도록 요청합니다.

호스트에서 게이트웨이에 접근하는 주소는 `http://localhost:4100`입니다. API 컨테이너에서는 `http://metricflow:4100`을 사용합니다. Cube와 dbt 예제는 DB, 연결 설정과 Runs가 분리됩니다. Recipe는 각각 `recipes/`, `recipes-dbt/`에 저장됩니다. 포트가 같으므로 [샘플 안내](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)의 종료 명령으로 현재 예제를 종료한 뒤 전환하세요.

현재는 한 번에 하나의 연결을 사용합니다. Recipe의 지표 참조를 다른 제공자로 자동 변경하지 않으므로, 다른 연결에서 재사용하려면 지표·차원을 명시적으로 다시 선택해야 합니다. 기존 Run의 결과와 출처는 그대로 보존되며, 조회 권한은 기록된 소유자와 접근 규칙을 따릅니다.

dbt 예제에는 거래·상품·가구·캠페인·캠페인 접촉·쿠폰 사용 이력 모델이 있습니다. 거래 수취액·수량·장바구니 수·거래행 수·쿠폰 사용 비율·캠페인 수·접촉 건수·쿠폰 사용 건수를 분석할 수 있습니다. 각 사실 모델은 선언한 entity로 상품·가구·캠페인에 연결됩니다. 캠페인 접촉의 날짜 기준은 캠페인 시작일입니다. 원본에 없는 실제 접촉 시각은 만들지 않습니다. 가구 모델에는 사건 날짜가 없어 별도의 시간 기반 가구 수 지표를 위해 날짜를 꾸며 넣지 않습니다.

`examples/complete-journey/dbt/models/`에는 모델별 SQL과 YAML이 있습니다. SQL은 조회할 뷰를 만들고 YAML은 연결 키·차원·지표를 선언합니다. `sources.yml`은 원본 테이블의 위치입니다. 원본 쿠폰-상품 연결표와 프로모션 배치표는 거래가 중복 집계되지 않도록 두 예제 모두 분석 모델에 바로 연결하지 않습니다.

## 직접 운영하는 dbt 프로젝트 연결

API 서버와 별도의 Python 3.12 가상환경에 설치합니다.

```bash
python3.12 -m venv .venv-metricflow
.venv-metricflow/bin/pip install -e '.[metricflow]'
export DBT_PROJECT_DIR=/absolute/path/to/dbt-project
export DBT_PROFILES_DIR=/absolute/path/to/dbt-profiles
export DL_METRICFLOW_INSTANCE=production
export DL_METRICFLOW_TOKEN=your-gateway-access-token
.venv-metricflow/bin/uvicorn decision_layer.semantic.providers.metricflow.gateway:create_gateway \
  --factory --host 127.0.0.1 --port 4100
```

dbt 모델을 먼저 빌드하세요. 게이트웨이는 프로필의 기본 target을 사용하므로 데이터 조회 전용 계정으로 구성합니다. Sources에 게이트웨이 주소와 같은 연결 이름을 입력하고 접근 토큰을 설정합니다. Docker에서 호스트로 연결한다면 컨테이너 자신의 localhost 대신 서비스 이름 또는 `host.docker.internal`을 사용합니다.

게이트웨이 토큰은 하나의 공용 데이터 조회 계정에 대한 접근을 허용합니다. 사용자별 행 권한이나 authentik/JWT 클레임을 해석하는 기능은 포함하지 않습니다. 이런 권한이 필요하면 게이트웨이와 데이터 저장소에서 처리해야 합니다. 인증 없는 예제 환경을 외부에 공개하지 마세요.

## 분석에 필요한 메타데이터

기존 semantic 모델에 Decision Layer 전용 `meta`를 추가할 필요가 없습니다. 사용 가능한 차원은 MetricFlow에서, 지표 이름·설명·집계 방식은 기본 semantic manifest에서 읽습니다. `count` 지표는 자체 건수를 사용하고, `ratio` 지표의 분자·분모는 기본 `type_params`에서 읽습니다. `config.meta.decision_layer`로 분석 의미를 보완하지 않습니다.

일반 계산식인 `derived` 지표를 통계적 비율로 추정하지 않습니다. 예제의 쿠폰 사용 비율은 기존 백분율 계산과 값을 그대로 유지합니다. 드릴다운·추이·기술적 집단 비교는 사용할 수 있지만, 확인되지 않은 분모나 표본 수를 다른 건수 지표로 대신하지 않습니다. 신뢰구간·최소 표본 검사·조건 맞춤 비교에 필요한 정보가 없으면 해당 기능을 제한합니다. 따라서 예제의 쿠폰 사용 비율로 CEM을 실행하면 근거 없는 통계 결과 대신 실행할 수 없는 이유를 반환합니다.

드릴다운·추이·집단 비교·범주형 조건 CEM을 지원합니다. 개체 단위 데이터 추출과 미지원 필터·날짜 기준은 실행 전에 거절합니다. 요청에는 공통 데이터 명세만 받을 수 있으며 임의 SQL이나 코드는 실행하지 않습니다. 최대 50,000행까지 조회하고 MetricFlow 요청과 선택적 SQL 실행 근거를 남깁니다.

## 같은 결과인지 확인하기

두 서비스가 켜진 상태에서 저장소 루트에서 실행합니다.

```bash
DL_METRICFLOW_TEST_URL=http://127.0.0.1:4100 \
  .venv/bin/pytest tests/provider/test_metricflow_live.py -q
```

세 가지 기술적 분석의 결과가 Cube와 MetricFlow에서 같은지, 표본 정보가 없는 CEM은 안전하게 거절되는지 확인합니다. 제공자 호환성 검사이며 인과 해석의 타당성을 보증하지 않습니다.
