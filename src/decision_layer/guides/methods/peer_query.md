---
name: analysis.peer_comparison
version: 1.0.1
description: 명시한 조사 대상과 동료 집단을 같은 범위의 Cube 쿼리로 조회하고 근거를 기록합니다.
query_execution: true
roles:
  metric: {kind: measure, default_binding: primary_metric}
  dimensions: {kind: dimension, multiple: true, required: false, default_binding: preferred_dimensions}
parameters:
  filters: {type: filters, default: []}
  subject:
    type: drill_path
    required: true
    meaning: comparison_subject
    source_policy: {allowed: [literal, input, step], default: previous_result, project: condition}
  population: {type: drill_path, default: [], meaning: comparison_population}
---
# 조사 대상과 동료 집단 비교

클라이언트 AI가 run_skill_query로 수행하는 단계다.

1. 앞 단계에서 받은 subject(selected_group의 condition), 지표·기간·population을 읽는다. 어떤 집단이 업무상 적절한 peer인지 확인한다. 관측된 차원이 자동으로 적절한 비교군이 되지는 않는다.
2. 대상의 동등 조건과 모든 상속 population·filters·Run 필터를 적용해 대상을 집계 조회한다. 공식 집계를 유지한다. 표본 수가 필요하면 소스가 선언한 count 지표를 발견한 후 사용한다.
3. 같은 기간·시간 차원·공통 범위로 peer를 별도 조회하고 notEquals로 대상을 제외한다. 대상 전용 조건을 공통 population에 넣지 않는다. population이 비어 있으면 '접근 가능한 집단 중 대상 제외'라고 명시하고 위험 조정된 비교군이라고 부르지 않는다.
4. 더 나눠보려면 발견한 차원으로 peer를 조회하고 대상 제외 조건을 유지한다. 각 쿼리의 목적·실패·결과를 이 단계에 기록한다. 모든 조회에 limit_rows <=1000을 명시한다. 처음 25행 이후는 get_skill_query로 확인한다.
5. 후속 선택은 실제 query_id·절대 행 인덱스·dimension·reason을 가리켜야 한다. condition/path는 동등 조건 경로만 담는다. 전체 범위는 selected_group.evidence.filters로 전달하며 대상 제외·범위 조건도 보존한다. 다음 Skill의 filters 또는 Python DataInput의 filters_parameter에 $steps.STEP_ID.selections.selected_group.evidence.filters를 연결한다.
6. finish_skill_step으로 완료하거나 거부하면 Recipe가 이어진다. 후속 Python은 Recipe가 바인딩한 지표·개체와 전체 집단 필터를 받고 자신의 입력 검사를 수행한다. 임의 분석 코드를 만들거나 집단 차이로 인과 관계를 주장하지 않는다.

실행기는 조회 권한·바인딩 지표·기간·상속 필터를 검사한다. 동료 집단의 적절성, 모든 지침의 준수, 동일 노출 여부, 통계 검정 여부는 자동 검증하지 않는다. 표본 수가 없으면 적합성 미확인으로 기록한다. 조회 표는 근거이며 설명은 호출자가 작성한 해석이다.
