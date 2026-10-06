---
title: Method 기여하기
description: 검증 가능한 분석 기능을 공통 실행 엔진에 추가합니다.
---

# Method 기여하기

Method는 입력, 실행 조건, 결과 형식이 정해진 분석 기능입니다. 기존 Method를 다른 순서나 설정으로 쓰는 것만 필요하다면 [Recipe](./recipes.md)를 만드세요.

## 시작할 코드

### 입력 선언으로 편집 화면 만들기

Role에 `label`과 `default_binding="primary_metric"`을 지정하면 Recipe 지표를
기본으로 사용합니다. 파라미터는 타입, 표시 이름, 필수 여부, 범위와 `ui_group`
(`basic`, `options`, `hidden`)을 선언합니다. `semantic_kind`는 카탈로그 선택창을,
`visible_when`은 다른 파라미터 값에 따른 표시 조건을 지정합니다.
별도 React 화면을 작성할 필요는 없습니다. 숨긴 입력도 명시된 값은 보존합니다.

일반 단계 편집에는 필수 역할과 기본 입력만 표시합니다. 선택 역할과 엔진의
세부 설정은 Recipe 코드 보기에서 확인·수정합니다. 기간이 필요한 Method는
`requires_period=True`를 선언하세요. 결과 확인을 누른 뒤에만 기간을 받습니다.
기간이 필요한 비교를 켜는 boolean 입력은 `meaning="period"`로 선언할 수 있습니다.
프런트엔드에 Method 이름별 분기를 추가하지 않습니다.

여러 값의 역할은 `editor_parameter`에 대응하는 단일 semantic 파라미터를
명시할 수 있습니다. 드릴다운은 기존 분류 목록을 유지하면서 이 단계에서
실제로 나눌 항목 하나만 보여 줍니다. 파라미터 이름으로 관계를 추측하지 않고
manifest가 명시한 관계를 검사합니다.

그룹 입력에 `InputSourcePolicy`를 선언하면 직접 지정, 앞 단계 결과, 실행 입력 중
허용할 출처와 기본 연결을 정할 수 있습니다. `previous_result`는 가장 가까운 앞
단계의 정렬 결과를 연결하고, `parameter_parents`는 다른 입력이 선택한 대상의
상위 조건을 비교 집단으로 사용합니다. 앞 단계가 없는 필수 대상은 기본값 없는
실행 입력이 됩니다. Python의 `configure_step`과 REST의
`POST /recipes:configure-step`은 같은 명세를 만듭니다. 실행할 때 완전성, 동점과
접근 권한은 다시 검사합니다. 통계·ML 계산은 검토한 Python 코드에 구현하며
선언에 실행 코드나 프런트엔드 플러그인을 넣지 않습니다.

[실행 가능한 기여 템플릿](https://github.com/haechangcho/decision-layer/tree/main/examples/method-template)에는 Method 계약과 독립 테스트가 있습니다. Method는 검토한 Python 코드로 서버에 설치됩니다. 웹에서 사용자 코드를 올리거나 AI가 생성한 코드를 실행하지 않습니다.

1. `src/decision_layer/methods/` 아래에 모듈을 추가합니다.
2. Manifest에 이름, 버전, 입력 역할, 파라미터, 결과와 해석 범위를 선언합니다.
3. `ctx.dataset(DatasetSpec(...))`으로 필요한 데이터 단위와 열을 요청합니다.
4. 결과, 검증, 경고와 실행 근거를 반환합니다.
5. 누락 입력, 작은 표본, 지원하지 않는 가정, 알려진 결과에 대한 테스트를 추가합니다.

지표 SQL, 조인과 접근 권한은 Cube에 남겨야 합니다. 통계·ML 라이브러리는 사용할 수 있지만 의존성과 버전을 명시하고, 데이터 추출 한계와 해석 조건을 테스트해야 합니다.

전체 계약과 코드 링크는 [영문 Method 가이드](/guides/methods)에 있습니다.

## 평균 지표의 조건 맞춤 비교

`causal.cem@1.1.0`은 원본에서 평균으로 선언된 지표에 `sample_count`를 명시적으로 받을 수 있습니다.
두 지표에 동일한 원본 기본 키가 선언되어 있고 조회 가능해야 합니다. 각 기본 단위에 행 수 1과 누락되지 않은
유한한 결과값이 있는지 확인합니다. 인접 지표나 SQL 표현으로 표본 의미를 추측하지 않으며, 계약이 불명확하면 거절합니다.
현재 공식 hosted dbt API의 metadata만으로는 이 경로를 확인할 수 없습니다.

연속형 평균의 불확실성 계산은 지원하지 않습니다. 결과에 `statistical_judgement: not_tested`를 기록하며
평균을 비율용 유의성 검정에 넣지 않습니다.
[캠페인 예제](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/CAMPAIGN_ANALYSIS.ko.md)는
Cube·로컬 MetricFlow의 일치와 표본 부족 시 거절을 보여 주는 예제이며, 인과 효과의 정답을 제공하지 않습니다.
