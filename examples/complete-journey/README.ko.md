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
Runs에서 질문·지표·분석 단계를 확인하고, 필요한 단계를 Recipe 초안으로 검토하세요.

> 364 매장의 식료품 쿠폰 사용 비율을 다른 매장 및 전체 집단과 비교해줘.

동료 비교는 대상을 제외한 집단의 지표와 차이를 보여줍니다. 이상 행위나 인과 효과를 단정하지 않습니다.

주의 사항:
- 원본의 DAY는 상대 일자입니다. Cube 날짜는 1일을 2000-01-01로 매핑한 **가상 달력**이며 실제 구매 연도가 아닙니다.
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
전체 구조와 로컬 개발은 [영문 가이드](README.md)를 참고하세요.
