# Method 작성 패턴

Method의 조회 형태를 아래처럼 분류합니다. 이 구현 범위에서 겹치지 않도록 데이터 grain과 추출 횟수로 구분했습니다. 모든 통계 알고리즘·데이터 형태를 지원한다는 뜻은 아닙니다. 동일 함수와 등록·실행 모델을 사용하며, 알고리즘마다 별도 plugin 인터페이스를 만들지 않습니다.

| 패턴 | 데이터 접근 → 조합 | 실행 사례 |
| --- | --- | --- |
| A | 집계 조회 1개 → 직접 반환 | by-group, trend |
| B | 집계 조회 여러 개 → scalar/table 조합 | period, peer |
| C | 개체 데이터 1개 → 통계 알고리즘 | ols, dowhy, econml |
| D | 개체 데이터 여러 개 → 동일 개체 정렬 | unit-change, unit-change-wide |
| E | 개체 × 시간 데이터 1개 → 패널 알고리즘 | did |
| F | 개체 × 시간 데이터 여러 개 → 패널 결합 | did-split |
| G | 집계와 개체 데이터 → 혼합 결과 | mixed |

## A. Drilldown·추이

기간과 공통 필터는 실행 입력입니다. 함수는 measure·group 또는 time bucket만 선택합니다. 누락된 bucket을 0으로 채우거나 top-N을 전체 모집단으로 취급하지 않습니다.

<<< @/../examples/methods/scenarios/methods.py#series

## B. 여러 조회의 조합

“같은 함수 안에서 작성”은 한 Method 실행이 아래 세 `await ctx.aggregate(...)`를 순서대로 호출하고, 반환된 세 값을 Python으로 조합한다는 뜻입니다. 세 함수·세 등록·세 Recipe step을 만들 필요가 없습니다. 각 요청은 별도 label·budget·provenance를 갖고, 두 번째 조회가 실패하면 첫 번째 근거도 남습니다. 현재 예시는 순차 실행이며 provider snapshot 일치는 보장하지 않습니다.

`peers`는 비교 집단 조건이고 `subject`는 대상 조건입니다. 실행의 공통 필터는 세 조회에 모두 적용됩니다. 대상 dimension을 공통 필터에 넣으면 전체 비교가 깨지므로 거절합니다. 대상과 제외 조건의 권한은 동일 provider가 적용합니다.

<<< @/../examples/methods/scenarios/methods.py#peer

<<< @/../examples/methods/scenarios/methods.py#period_difference

## C–G. Entity와 panel

`ctx.entities(entity=unit, measures=..., dimensions=...)`는 provider가 선언한 분석 단위의 완전한 데이터를 요구합니다. `by_time`·`time_granularity`가 있으면 key는 unit × bucket입니다. 개체 통계에 top-N을 사용하지 않습니다. `stats.ols`, `stats.binary_regression`, `stats.linear_dml`은 같은 추출 형태에 다른 알고리즘을 적용합니다.

`query.unit_change`는 두 기간 또는 provider가 정의한 pre/post measure를 같은 unit으로 outer join하고 양쪽 개체 집단이 동일한지 확인합니다. `stats.two_period_contrast`의 `windows` 생략은 단일 panel, disjoint windows 지정은 분할 panel이며 동일 Method입니다. `query.unit_distribution`은 전체 provider 집계와 개체 분포를 함께 반환합니다.

[고급 분석의 인자 매핑·가정](statistical-methods.md)과 [12개 실행·13개 실패 시나리오](method-scenarios.md)에서 직접 확인하세요. 스트리밍·생존분석·다중 처치·복잡한 longitudinal inference는 이 예제의 지원 범위가 아닙니다.
