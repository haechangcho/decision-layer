# 캠페인 대상·비대상 가구 비교

importer가 `journey.campaign_household_outcomes`를 생성하고 다음 import 때 갱신합니다.
Cube와 dbt는 이 모델의 같은 대상 행을 읽습니다. 원천 테이블은 그대로 유지합니다.
**한 행은 캠페인 하나와 가구 하나**입니다. 거래행이나 쿠폰 사용 이력이 분석 단위가 아닙니다.

## 분석 정의

- 대상: 해당 캠페인의 중복 제거된 대상 명단에 있는 가구. 비대상: 그 명단에 없는 가구.
- 이전 기간: 시작 30일 전부터 시작일 전날까지.
- 이후 기간: 시작일부터 29일 뒤까지.
- 분석 모집단: 전후 기간이 데이터 전체 날짜 범위에 포함되고 이전 30일에 구매한 가구.
- 결과 지표: 이후 30일 가구당 평균 판매금액. 분석 모집단 중 이후 구매가 없는 가구는 0으로 포함합니다.
- 이전 판매금액 구간: 50 미만, 50~150 미만, 150~300 미만, 300~600 미만, 600 이상 달러.
- 이전 구매 빈도 구간: 장바구니 1~2회, 3~5회, 6~10회, 11회 이상.
- 가구 특성은 원본의 익명 코드입니다. 누락값을 임의 집단으로 바꾸지 않으며, 맞춤 조건에 쓰면 제외됩니다.
- 다른 캠페인 중첩 건수: 전후 관찰 기간과 겹치는 다른 캠페인의 대상 명단 포함 건수입니다.

날짜 선택은 **캠페인 시작일**에 적용됩니다. 각 캠페인의 전후 30일 집계를 잘라내지 않습니다.
가구 비교에는 캠페인 하나를 선택하세요. 여러 캠페인을 합치면 같은 가구가 반복되며 독립 표본으로 볼 수 없습니다.
30일과 구간 경계는 예제 모델의 정의입니다. 다른 기간을 쓰려면 모델을 변경·버전 관리해야 합니다.

전체 데이터의 날짜가 충분하다고 가구별 관측이 완전한 것은 아닙니다. 가구 목록도 구매자에서 만들어진 것이므로
전체 고객 명부가 아닙니다. 실제 수신일이 없고, 대상 선정은 무작위가 아니며 비대상도 다른 캠페인을 받을 수 있습니다.
**조건을 맞춘 차이는 캠페인 인과 효과를 입증하지 않습니다.**

## MCP에서 질문하기

> 8번 캠페인의 대상 가구는 비대상 가구보다 시작 후 30일간 가구당 평균 판매금액이 높았어?
> 이전 30일 구매금액과 구매 빈도 구간으로 CEM 비교해줘. 이어서 가구 특성도 추가한 비교를 해보고,
> 비교 불가하면 그 이유와 제외 표본을 알려줘. 두 단계를 하나의 Run에 기록하고 유의성이나 인과 효과는 단정하지 마.

캠페인 8은 예제 달력의 2001-02-15에 시작합니다. 이 날짜를 포함한 기간을 명시하세요.
`causal.cem`의 `sample_count`에는 캠페인·가구 관측 수 지표를 넣습니다.
지표·차원 이름과 설정은 [영문 계약표](CAMPAIGN_ANALYSIS.md#execute)를 참고하세요.

결과는 맞춤 전후 평균과 표본 유지율입니다. **평균 판매금액의 신뢰구간·통계적 유의성은 아직 지원하지 않습니다.**
가구 특성까지 맞추면 결측과 희소한 조건 조합으로 비교 불가가 될 수 있습니다. 결과를 얻으려고 기준을 낮추면 안 됩니다.

dbt 예제는 로컬 MetricFlow로 검증합니다. 현재 공식 hosted dbt API의 metadata만으로는 이 평균·행 수·기본 단위 계약을
확인할 수 없어 제품의 해당 경로는 여전히 거절합니다. SQL 추측이나 전용 meta로 우회하지 않습니다.

## 기존 환경 업데이트

Cube 예제 폴더에서:

```bash
docker compose build import api
docker compose run --rm --no-deps import
docker compose up -d --no-deps --wait cube api
```

dbt 예제 폴더에서:

```bash
docker compose -f compose.yaml -f compose.dbt.yaml build import dbt-setup metricflow api
docker compose -f compose.yaml -f compose.dbt.yaml run --rm --no-deps import
docker compose -f compose.yaml -f compose.dbt.yaml run --rm --no-deps dbt-setup
docker compose -f compose.yaml -f compose.dbt.yaml run --rm --no-deps dbt-setup dbt test --target setup --project-dir /project --profiles-dir /project
docker compose -f compose.yaml -f compose.dbt.yaml up -d --no-deps --wait metricflow api
```

볼륨 삭제나 원천 재다운로드는 필요 없습니다. 집계 갱신 중에는 새 모델에 잠금이 걸리므로 분석 중 갱신하지 마세요.
첫 설치는 기존 시작 명령으로 자동 구성됩니다. CEM은 1.1.0으로 올라갔으므로 이전 버전으로 고정한 Recipe는 검토 후
명시적으로 업데이트해야 합니다. 기존 Run은 바꾸지 않습니다.
