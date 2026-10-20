---
name: analysis.drilldown
version: 2.0.0
description: 실제 Cube 조회를 기록하며 지표를 차원별로 나누고 조사할 집단을 선택합니다.
query_execution: true
roles:
  metric: {kind: measure, default_binding: primary_metric}
  dimensions: {kind: dimension, multiple: true, required: false, default_binding: preferred_dimensions}
parameters:
  filters: {type: filters, default: []}
  population: {type: drill_path, default: [], meaning: comparison_population}
  comparison: {type: date_range}
---
# 항목별 드릴다운 조사

이 단계는 클라이언트 AI가 공통 조회 도구를 실행하는 Skill이다.

1. 바인딩한 지표·차원, Run 기간, 상속 population과 filters를 확인한다. 빠진 차원은 search_semantic으로 발견한다. 존재하지 않는 필드나 공식 정의를 만들지 않는다.
2. 해당 run_id/step_id의 run_skill_query를 호출한다. aggregate DatasetSpec에 바인딩한 measures, 발견한 dimensions, 명시한 time.dimension·date_range, order, limit_rows(1~1000), 모든 상속 조건과 Run 필터를 전달한다. 각 쿼리에 고유 ID와 목적을 기록한다.
3. 기간 비교는 이 단계의 comparison 입력이 명시된 경우에만 period_role=comparison으로 조회한다. 이전 기간을 임의로 추정하거나 비율을 합산하거나 미등록 이상 점수를 계산하지 않는다. 조회된 기간별 값을 근거로 설명한다. 변화율·분해·유의성 계산이 필요하지만 현재 제공되는 Method에 해당 계산이 없다면 지원하지 않는다고 알리고 그 주장은 중단한다. 임의 Python이나 머릿속 계산으로 대체하지 않는다.
4. 실제 조회 행과 경고를 확인한다. 한도는 전체 모집단을 봤다는 증거가 아니다. 응답은 처음 25행이므로 나머지는 get_skill_query로 읽는다. 유일한 선두가 필요한데 동률이면 선택을 확인하거나 이유를 적어 refused로 중단한다. 미리 합의된 동률 규칙만 명시적으로 적용한다.
5. 한 집단을 이어서 조사하려면 finish_skill_step의 selection에 실제 query_id, 0부터 시작하는 **절대 행 인덱스**, dimension 참조와 reason을 모두 넣는다. 페이지 안 순번은 offset을 더한다. 서버는 해당 값과 동등 필터 경로를 selected_group에 복사하며, 이상 판단이나 선택 이유의 진실성을 보증하지 않는다.
6. 데이터·범위가 부적절하면 refused로 종료한다. 완료하면 다음 Recipe 단계로 이어진다. 활성 Skill 도중 다른 Method의 run_step을 호출하지 않는다. 중단 후 get_run으로 확인하고 실패·중단된 조회는 새 query ID로 수정한다.

결과는 실제 조회 표와 선택 근거가 연결된 selected_group이다. 다음 집단 전체 조건을 전달하려면 selected_group.evidence.filters를 사용한다. 지침과 설명 자체는 계산 근거나 실행된 Validator가 아니다. 모든 단계와 근거를 확인한 후 Run 결론을 저장한다.
