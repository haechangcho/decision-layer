# Complete Journey

Databricks의 [데이터 준비 예제](https://www.databricks.com/notebooks/segment-p13n/sg_01_data_prep.html)에서 사용한 소매점 데이터입니다.
원본의 고객·상품·거래·캠페인·쿠폰 관계를 로컬 PostgreSQL과 Cube로 연결합니다. Databricks 계정은 필요하지 않습니다.

저장소 루트에서:

```bash
cd examples/complete-journey
docker compose up -d --build --wait --wait-timeout 900
```

**http://127.0.0.1:3000** 으로 접속하세요. 연결은 자동 설정되고 Recipe는 빈 상태로 시작합니다.
첫 실행에는 공식 원본 약 128 MB 다운로드와 8개 테이블 적재로 몇 분이 걸립니다. 이후에는 재사용합니다.
Web 3000, API 8000, Cube 4000, PostgreSQL 5433이 기본 포트입니다.
다른 서비스가 사용 중이면 `.env.example`을 `.env`로 복사해 포트를 바꾸세요.

MCP는 [연결 가이드](../../docs/guides/mcp.md)를 따라 API에 연결합니다. 질문 예시:

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 항목별로 나누고 근거도 보여줘.

독립 SQL 기준값은 **GROCERY, 4,093,814.14**입니다. 전체 수취액은 **8,057,463.08**입니다.
Runs에서 질문·분석 단계·설정·쿼리를 확인하고 **Recipe로 등록**을 누르면 실행한 절차와 설정이 그대로 저장됩니다. 변경이 필요하면 **편집해서 저장**을 선택하세요.

> 364 매장의 식료품 쿠폰 사용 비율을 다른 매장 및 전체 집단과 비교해줘.

동료 비교는 대상을 제외한 집단의 지표와 차이를 보여줍니다. 이상 행위나 인과 효과를 단정하지 않습니다.

거래 데이터 기간은 **2000-01-01 ~ 2001-12-11**입니다. 날짜 질문에는 **Transaction date(거래일)**를 사용하세요.
웹은 Cube가 제공한 추천 기간을 기본으로 선택합니다. MCP에서도 날짜 범위와 달력 설명을 확인할 수 있습니다.

> 2001년 7월부터 9월까지 수취액의 월별 추이를 보고 상품 부문별로 나눠줘.

주의 사항:
- DB에는 거래일·쿠폰 사용일·캠페인 시작일·종료일이 `DATE` 타입으로 저장됩니다. 원본의 상대 일수도 보존합니다.
- 날짜는 DAY 1을 2000-01-01로 변환한 **고정 예제 달력**입니다. 원본의 실제 구매 연도를 의미하지 않습니다.
- 공식 배포본의 인구통계는 코드로 익명화되어 있습니다. 실제 나이·소득으로 해석하지 않습니다.
- 수취액은 소매점이 받은 금액이며 고객 지불액이나 이익과 동일하지 않습니다.
- 캠페인 접촉은 무작위 처치가 아닙니다. 쿠폰 사용자는 처치 이후 선택된 집단입니다.
- 데이터는 저장소에 포함하지 않습니다. 이용·재배포 조건은 [출처 안내](NOTICE.md)를 확인하세요.

독립 SQL 검증 및 종료:

```bash
docker compose run --rm --no-deps import python verify.py
docker compose logs --tail=100 import cube api
docker compose down
```

`down`은 데이터와 Runs를 보존합니다. `down -v`는 이름 있는 볼륨을 삭제합니다.
기존 DB에는 아래 명령으로 날짜 컬럼을 추가할 수 있습니다. 원본 데이터는 다시 적재하지 않습니다.

```bash
docker compose build import
docker compose run --rm --no-deps import
docker compose restart cube api
```

전체 구조와 로컬 개발은 [영문 가이드](README.md)를 참고하세요.
