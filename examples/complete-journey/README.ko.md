# Complete Journey

Databricks의 [데이터 준비 예제](https://www.databricks.com/notebooks/segment-p13n/sg_01_data_prep.html)에서 사용한 소매점 데이터입니다.
원본의 고객·상품·거래·캠페인·쿠폰 관계를 로컬 PostgreSQL에 적재합니다. Cube 예제와 dbt MetricFlow 예제 중 하나를 선택할 수 있으며 Databricks 계정은 필요하지 않습니다.

dbt 예제에는 계정 없이 체험하는 용도의 로컬 게이트웨이가 포함됩니다. 회사의 기존 dbt 환경은 [공식 Semantic Layer API](../../docs/ko/guides/dbt.md)로 연결하며 예제 게이트웨이를 설치할 필요가 없습니다.

저장소 루트에서:

```bash
cd examples/complete-journey
docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900
```

위 명령은 **Cube 예제**를 실행합니다. **dbt 예제**는 대신 다음 명령으로 실행하세요.

```bash
docker compose -p decision-layer-dbt -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

선택한 제공자와 PostgreSQL·API·웹이 실행됩니다. **http://127.0.0.1:3000** 으로 접속하세요. 처음 설치하면 연결은 자동 설정되고 Recipe는 비어 있습니다. 기존 연결을 저장했다면 [연결 설정](http://localhost:3000/sources)에서 제공자를 선택하고 연결 테스트 후 저장하세요. 두 예제는 웹·API 포트가 같으므로 하나씩 실행합니다.
dbt의 모델 구조와 연결 방법은 [MetricFlow 가이드](../../docs/ko/guides/metricflow.md)에 있습니다.
첫 실행에는 공식 원본 약 128 MB 다운로드와 8개 테이블 적재로 몇 분이 걸립니다. 이후에는 재사용합니다.
Web 3000, API 8000, PostgreSQL 5433이 공통 포트입니다. Cube 예제는 4000, dbt 예제는 MetricFlow 4100을 사용합니다.
다른 서비스가 사용 중이면 `.env.example`을 `.env`로 복사해 포트를 바꾸세요.

MCP는 [연결 가이드](../../docs/guides/mcp.md)를 따라 API에 연결합니다. 질문 예시:

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 항목별로 나누고 근거도 보여줘.

독립 SQL 기준값은 **GROCERY, 4,093,814.14**입니다. 전체 수취액은 **8,057,463.08**입니다.
Runs에서 질문·분석 단계·설정·쿼리를 확인하고 **Recipe로 등록**을 누르면 실행한 절차와 설정이 그대로 저장됩니다. 변경이 필요하면 **편집해서 저장**을 선택하세요.

> 364 매장의 식료품 쿠폰 사용 비율을 다른 매장 및 전체 집단과 비교해줘.

동료 비교는 대상을 제외한 집단의 지표와 차이를 보여줍니다. 이상 행위나 인과 효과를 단정하지 않습니다.

거래 데이터 기간은 **2000-01-01 ~ 2001-12-11**입니다. 날짜 질문에는 **Transaction date(거래일)**를 사용하세요.
두 예제 모두 거래·상품·가구·캠페인·캠페인 접촉·쿠폰 사용 이력 모델을 정의합니다. 웹은 제공자에 추천 기간이 있으면 기본으로 선택합니다. 날짜 변환 설명은 각 차원 대신 이 안내에 정리했습니다.

> 2001년 7월부터 9월까지 수취액의 월별 추이를 보고 상품 부문별로 나눠줘.

두 제공자 모두 **캠페인 × 가구** 단위의 전후 30일 구매 모델도 제공합니다. 캠페인 하나를 선택해서 질문하세요.

> 8번 캠페인의 대상 가구는 비대상 가구보다 시작 후 30일간 가구당 평균 판매금액이 높았어?
> 이전 30일 구매금액과 구매 빈도를 맞춰 비교하고, 가구 특성까지 추가하면 비교 가능한 표본이 충분한지도 확인해줘.
> 두 단계를 하나의 Run에 남기고, 조건을 임의로 빼거나 통계적으로 유의하다고 주장하지 마.

정의·한계·기존 볼륨 업데이트는 [캠페인 분석 가이드](CAMPAIGN_ANALYSIS.ko.md)를 참고하세요.
평균 구매금액의 유의성 검정은 아직 지원하지 않습니다. 이 dbt 예제는 로컬 MetricFlow로 검증합니다.
현재 공식 hosted dbt API의 metadata만으로는 평균·표본 수·기본 단위를 검증할 수 없어 해당 CEM 경로를 지원하지 않습니다.

주의 사항:
- DB에는 거래일·쿠폰 사용일·캠페인 시작일·종료일이 `DATE` 타입으로 저장됩니다. 원본의 상대 일수도 보존합니다.
- 날짜는 DAY 1을 2000-01-01로 변환한 **고정 예제 달력**입니다. 원본의 실제 구매 연도를 의미하지 않습니다.
- 공식 배포본의 인구통계는 코드로 익명화되어 있습니다. 실제 나이·소득으로 해석하지 않습니다.
- 수취액은 소매점이 받은 금액이며 고객 지불액이나 이익과 동일하지 않습니다.
- 캠페인 접촉은 무작위 처치가 아닙니다. 쿠폰 사용자는 처치 이후 선택된 집단입니다.
- 데이터는 저장소에 포함하지 않습니다. 이용·재배포 조건은 [출처 안내](NOTICE.md)를 확인하세요.

독립 SQL 검증 및 종료:

```bash
docker compose -p decision-layer-cube run --rm --no-deps import python verify.py
docker compose -p decision-layer-cube logs --tail=100 import cube api
docker compose -p decision-layer-cube down
```

dbt 예제의 로그 확인과 종료에는 실행할 때와 같은 파일을 지정합니다.

```bash
docker compose -p decision-layer-dbt -f compose.yaml -f compose.dbt.yaml logs --tail=100 dbt-setup metricflow api
docker compose -p decision-layer-dbt -f compose.yaml -f compose.dbt.yaml down
```

예제를 바꿀 때는 위의 해당 예제 종료 명령을 실행한 뒤 다른 예제를 시작하세요. 포트가 같아 동시에 실행하지 않습니다. Cube와 dbt는 별도 DB, 연결 설정과 Run 볼륨을 사용합니다. Recipe 파일은 Cube의 `recipes/`, dbt의 `recipes-dbt/`에 각각 저장됩니다. 처음 실행한 예제는 Runs와 Recipes가 비어 있고, 선택한 semantic layer가 자동 연결됩니다. 다시 실행하면 해당 예제의 기록이 유지됩니다.

이전에 `decision-layer-journey` 또는 `decision-layer-onboarding`으로 실행했다면 먼저 같은 폴더에서 `docker compose -p decision-layer-journey down` 또는 `docker compose -p decision-layer-onboarding down`으로 종료하세요. 기존 볼륨은 삭제하거나 새 환경에 자동 복사하지 않습니다. 폴더를 바꿔 clone해도 같은 프로젝트 이름을 쓰면 볼륨이 재사용됩니다.

`down`은 데이터와 Runs를 보존합니다. `down -v`는 이름 있는 볼륨을 삭제합니다.
기존 DB에는 아래 명령으로 날짜 컬럼을 추가할 수 있습니다. 원본 데이터는 다시 적재하지 않습니다.

```bash
docker compose -p decision-layer-cube build import
docker compose -p decision-layer-cube run --rm --no-deps import
docker compose -p decision-layer-cube restart cube api
```

전체 구조와 로컬 개발은 [영문 가이드](README.md)를 참고하세요.
