---
name: analysis.trend
version: 1.1.0
description: 공식 지표의 시간별 추이를 조회하고 실제 관측값과 조회 범위의 한계를 설명합니다.
query_execution: true
roles:
  metric: {kind: measure, default_binding: primary_metric}
  related: {kind: measure, multiple: true, required: false}
parameters:
  filters: {type: filters, default: []}
  population: {type: drill_path, default: []}
  granularity: {type: enum, enum: [day, week, month, quarter], default: month}
  comparison: {type: date_range}
---
# 시간에 따른 추이 조사

1. 지표의 공식 집계·단위·시간 차원과 Run 기간을 확인한다. 일·주·월·분기 중 질문에 맞는 granularity를 사용한다. 과거 Run의 숫자를 현재 사실로 재사용하지 않는다.
2. `run_skill_query`에 `grain: aggregate`, 바인딩한 measures, `time: {dimension: 시간참조, date_range: Run기간, granularity: 선택단위}`, 시간 오름차순 order, 명시적인 limit_rows(최대 1000), 모든 상속 조건과 Run 필터를 전달한다. 지표별 평균·비율을 임의로 더하거나 평균내지 않는다.
3. 비교 기간은 comparison 입력에 명시된 경우에만 period_role=comparison으로 별도 조회한다. 비교 대상이 없으면 임의로 전월을 고르지 않는다. 각 쿼리의 기간·집계 단위·집단이 무엇인지 기록한다.
4. 반환된 시간 구간·null·누락·경고를 확인하고 필요한 다음 페이지는 `get_skill_query`로 읽는다. 관측 행만으로 모든 구간의 적재 완전성을 확인했다고 말하지 않는다. 누락 구간을 조용히 0으로 채우지 않는다.
5. 실제 표의 관측값을 근거로 추이를 설명하고 `finish_skill_step`으로 완료한다. 최대 변화·변화율·유의성·요인 분해 계산은 이 Skill이 제공하지 않는다. 현재 제공되는 Method에 필요한 계산이 없다면 그 주장은 중단하고 지원하지 않는다고 알린다. 임의 Python이나 머릿속 계산으로 대체하지 않는다. 활성 Skill 도중 다른 Method를 실행하지 않는다.
6. 검사 미구현·작은 표본·조회 실패를 숨기지 않는다. 데이터나 가정이 부족하면 refused로 중단하거나 확인하지 못한 내용을 명시한다. 최대 변화는 통계적 이상이 아니며 함께 움직임은 인과 관계가 아니다.

숫자 계산과 검사는 등록된 실행 코드의 Result에 근거한다. 이 Skill의 문장이나 완료 상태에는 분석 capability를 부여하지 않는다. 비교·계산이 필요한 goal은 실제 Python 단계의 근거에 연결한다.
