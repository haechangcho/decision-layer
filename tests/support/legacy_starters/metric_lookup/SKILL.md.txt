---
name: analysis.metric_lookup
version: 2.0.0
description: 공식 지표를 필요한 차원·기간·필터로 조회하고 실제 결과와 한계를 기록합니다.
query_execution: true
roles:
  metric: {kind: measure, default_binding: primary_metric}
  related: {kind: measure, multiple: true, required: false}
  dimensions: {kind: dimension, multiple: true, required: false}
parameters:
  filters: {type: filters, default: []}
  population: {type: drill_path, default: []}
---
# 지표 조회

1. 연결된 Cube에서 지표·단위·시간 차원·집계 의미를 확인한다. 공식 순매출과 매출을 조용히 바꾸지 않는다. 질문에 필요한 기간이나 대상이 모호하면 확인한다.
2. 이 Run과 활성 step_id에서 `run_skill_query`를 호출한다. `spec`은 `grain: aggregate`, 바인딩한 `measures`, 발견한 `dimensions`, 명시적인 `time.dimension`·`time.date_range`, `filters`, `limit_rows`(1~1000)로 구성한다. 상속받은 population·filters와 Run 필터를 빠뜨리지 않는다. 정렬이 필요하면 조회 지표나 시간 차원을 사용한다.
3. 실제 값과 검사·경고를 확인한다. 응답은 처음 25행이므로 남은 행은 `get_skill_query`의 next_offset으로 읽는다. 전체 행을 확인하지 않고 전체 분포를 봤다고 말하지 않는다. 조회 성공이 지표 의미·완전성·인과성을 보증하지 않는다.
4. 값이 없거나 필요한 의미를 확인하지 못하면 `finish_skill_step(status="refused", reason=...)`로 중단한다. 그렇지 않으면 조회 근거를 적어 단계를 완료한다. 집단을 다음 단계에 넘겨야 한다면 실제 query_id·절대 행 인덱스·dimension·reason을 selection에 지정한다.
5. 결과 숫자를 새로 계산하거나 통계적 차이·원인을 주장하지 않는다. 계산이 필요하면 이 Skill을 완료한 뒤 등록된 Python Method를 별도 단계로 실행한다. 모든 단계가 끝난 후 근거에 연결한 결론을 저장한다.

이 Skill의 본문은 분석 지침이다. 실제 쿼리·권한·기간·필터 검사는 실행기가 기록하며, 지침을 읽은 것만으로 검사 통과를 부여하지 않는다.
