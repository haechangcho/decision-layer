---
name: guide.breakdown
version: 1.0.1
description: 지표를 항목별로 나눠보고 범위·기간·해석 한계를 확인하는 참고 지침입니다.
suggested_methods: [analysis.metric_lookup, analysis.drilldown, analysis.trend]
---
# 항목별 나눠보기 참고 지침
공식 지표·기간·그룹 차원을 발견한다. 전체 규모는 analysis.metric_lookup, 항목별 조사는 analysis.drilldown, 시간 추이는 analysis.trend로 실제 실행한다. 필요한 계산은 별도 등록 Python 단계로 연결한다. 잘못된 grain·작은 표본·불완전 기간을 숨기지 않는다. 비가산 지표를 합산하거나 큰 차이를 원인으로 단정하지 않는다.
