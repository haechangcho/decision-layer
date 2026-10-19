# Method 계약

입력·출력·편집 화면 동작을 선언할 때 참고하는 문서입니다.
실행 가능한 예제부터 시작하려면 [첫 Method 개발](../guides/methods.md)을 보세요.


## 함수 작성 API와 내부 계약

권장 경로는 `@method(...)`와 typed keyword 인자입니다. `Measure`, `Dimension`, `TimeDimension`, `Entity`, `DateRange`, `Equality`, `list[Filter]`, `AnalysisDesign`을 사용합니다. 역할·일반 파라미터·결과 타입은 signature에서 기존 `MethodManifest`로 변환됩니다. `requires_packages`는 검증할 설치 버전이며 런타임 설치 지시가 아닙니다. 지원하지 않는 annotation은 등록 전에 오류가 납니다.

- `ctx.aggregate(...)`: provider 집계. 명시적인 top-N 또는 bounded complete extraction.
- `ctx.entities(...)`: 선언된 primary unit의 완전한 관측. 시간 bucket이 있으면 unit × time key.
- `ctx.compute(fn, ...)`: credential 없이 순수 계산. 직접 trial은 현재 프로세스, server/preview는 종료 가능한 자식 프로세스.
- `Table`, `Estimate`: JSON-compatible artifact. 유한값과 payload 형태를 검사합니다.

`Table.from_dataset(data)`는 행 목록을 `primary.data`에, 열의 이름과 semantic 경로,
역할, 시간 단위를 `primary.columns`에 보존합니다. 그룹별 조회와 월별 추이는 같은
반환 타입을 사용합니다. 웹은 시간 구간 열 하나와 지표가 있고 추가 그룹이나 entity
열이 없는 결과에 추이 그래프를 표시합니다. 다른 결과는 표로 표시합니다.
`Table(rows)`의 문자열이 날짜처럼 보인다는 이유로 시간축을 추측하지 않습니다.
기존 `TimeSeries` Method와 저장된 `time_series` 결과는 호환 지원합니다.
`time_series` 같은 분석 capability와 결과 표시 타입은 별개입니다.

새 Method는 관측 데이터의 요약과 관계 분석에 `interpretation="association"`을
사용합니다. 그룹별 조회, 추이, 회귀의 연관성 분석을 포함하며 인과효과를 보장하지
않습니다. `causal_conditional`의 가정에 따른 해석 계약은 유지합니다.
기존 `descriptive`, `associational` 값과 실행 기록, 설치된 builtin 버전은 보존합니다.
Association 목표는 필요한 capability와 semantic 참조가 맞으면 기존 두 비인과
분류의 결과도 사용할 수 있습니다. 기존 목표의 검증 규칙은 유지하므로 Recipe
계약을 바꿀 때는 목표도 명시적으로 수정합니다.

Python과 REST/MCP의 measure/dimension/entity maps는 canonical bindings로 정규화합니다. REST는 `POST /methods/{name}:run` 또는 `POST /runs/{id}/steps`를 사용합니다. Recipe step에는 canonical bindings/params를 저장하고, 기존 바인딩도 계속 받습니다. Web은 같은 manifest의 역할 종류와 structured parameter를 표시하며 별도 분석 코드를 갖지 않습니다.

고급 변수 역할은 명시적으로 measure/dimension 양쪽을 허용할 수 있습니다(`accepted_kinds`). `Entity`는 provider가 primary dimension으로 선언한 참조여야 합니다. 조건·필터에 나온 객체도 catalog/권한 검증을 받습니다. 공통 scope filter는 제거할 수 없으며 현재 조회는 Run 기간을 확장할 수 없습니다. 비교 기간은 명시적인 policy 경로를 사용합니다.

기본 완전 추출은 50,000행, 선택 alias 최대 100열과 200만 cell이며 server policy의 더 작은 행 제한이 우선합니다. overflow sentinel을 조회해 잘린 표본을 성공 처리하지 않습니다. 통계 encoding도 최대 100열·200만 cell을 제한합니다. 최대 30개 filter/window, query budget/deadline과 시도 기록이 적용됩니다. 다중 조회의 warehouse snapshot 일치는 보장하지 않습니다.

각 Result는 버전, canonical spec, query attempts/labels, 설치된 요구 라이브러리 버전, Python, 검증·경고를 기록합니다. 일반 class의 자유로운 artifact payload는 별도 독립 테스트가 필요합니다. [실행 가능한 작성 가이드](../guides/methods.md)와 [시나리오](../guides/methods.md)를 먼저 사용하세요.

아래 class API는 추가 artifact·선택·복잡한 계약이 필요한 경우의 기존 확장 경로입니다. 단순 Method에서 manifest를 수동 중복 작성할 필요는 없습니다.

## 구현과 등록

Method는 서버에 설치하는 검토된 Python 코드입니다. Manifest는 계약을 선언하고
`run()`이 계산을 구현합니다. 동적 설치나 코드 업로드 실행기는 제공하지 않습니다.
웹·Python·REST·MCP가 같은 계약을 사용합니다.

1. `src/decision_layer/methods/`에 `Method` 하위 클래스를 추가합니다.
2. `MethodManifest`에 이름·버전·역할·파라미터·실행 모드·해석 범위·artifact 타입을 선언합니다.
3. `async run(ctx, bindings, params) -> MethodOutput`을 구현합니다.
4. `ctx.dataset(DatasetSpec(...))`으로 필요한 열과 grain을 조회합니다.
5. `methods/__init__.py`의 `register_builtins()`에 구현을 추가합니다. 모듈은 import만으로 자신을 등록하지 않습니다.
6. 독립적인 정답·실패 테스트를 추가합니다. 사용자 메시지는 번역 도우미를 사용하고 `i18n/ko.json`에 한국어를 추가합니다.

지표 수식·join·권한은 시맨틱 provider에 둡니다. 원본 쿼리로 실행 context를 우회하지 않습니다.
하나의 Method에서 여러 Dataset을 조합할 수 있습니다.
기존 Method로 계산할 수 있다면 [Recipe](../guides/recipes.md)를 사용합니다.

## 입력과 편집 화면 선언

| 선언 | 동작 |
| --- | --- |
| Role `label`, `default_binding="primary_metric"` | 역할을 표시하고 Recipe 지표를 기본 입력으로 사용 |
| Role `exclusive_group` | 대체 scalar 역할을 제시하며 유효한 Recipe는 정확히 하나를 선택 |
| Role `editor_parameter` | 여러 값의 역할과 이 단계가 사용할 단일 시맨틱 입력을 연결 |
| Parameter `type`, `required`, 범위 | 입력값 검증 |
| Parameter `label`, `ui_group` | `basic`·`options`·`hidden`으로 입력을 구성하며 `advanced`도 호환 |
| Parameter `semantic_kind` | 카탈로그 객체 선택 |
| Parameter `visible_when` | 다른 선언된 파라미터에 따라 입력 표시 |
| Group parameter `semantic_role` | 시맨틱 기준 옆에 그룹 입력 표시 |
| Manifest `requires_period=True` | 결과 확인 시 기간 요구 |
| Boolean parameter `meaning="period"` | 기간이 필요한 계산을 켜는 옵션임을 선언 |

일반 단계 편집은 필수 역할·대체 역할·기존 연결·기본 파라미터를 보여 줍니다.
나머지 연결과 세부 설정은 Recipe 코드에서 확인합니다. 명시적으로 입력한 숨김 값도 확인할 수 있습니다.
그룹 기준을 바꾸면 고정되지 않은 그룹 정의만 초기화하고 검증 기준은 유지합니다.
이 입력을 위해 Method 이름별 프런트엔드 분기나 별도 패널을 추가하지 않습니다.

원본 평균은 `default_binding="unit_count"`인 건수 역할을 선언할 수 있습니다.
`configure_step(..., catalog=catalog)`는 호출자 카탈로그에 같은 기본 단위의 원본 행 건수가
정확히 하나 선언되어 있을 때만 연결합니다. 그 외에는 입력을 요구하며 기존 선택은 유지합니다.
실행 시 개별 단위 검사도 적용합니다.

## 입력 출처

그룹 입력은 다음처럼 선언할 수 있습니다.

```python
InputSourcePolicy(
    allowed=["literal", "step", "input"],
    default="previous_result",
    project="condition",
)
```

`previous_result`는 해당 기능을 제공하는 가장 가까운 앞 단계에서 첫 번째 순위 그룹을 선택합니다.
`parameter_parents`는 다른 파라미터의 단계 출처에서 비교 집단을 구성합니다.
필수 대상이 없으면 기억된 값 없이 타입이 있는 실행 입력이 됩니다.
Python `configure_step(recipe, index)`와 REST `POST /recipes:configure-step`은 같은 명세를 만듭니다.
실행 시 완전성·모호성·권한을 검사합니다. Manifest 표현식이나 프런트엔드 플러그인에 분석 코드를 넣지 않습니다.

## 출력과 기능

`MethodOutput`으로 기본 artifact·보조 artifact·검증·경고를 반환합니다.
반환하는 모든 artifact 타입을 선언합니다. Registry는 선언하지 않은 artifact 타입·선택·기능을 거절합니다.
출력 payload와 수치는 Method 테스트로 검증합니다.

Manifest의 `provides`에 `metric_lookup`·`matched_comparison` 같은 안정적인 기능 이름을 선언합니다.
Recipe 후보와 Run 목표는 표시 이름 대신 이 기능을 사용합니다.
`provides_when`은 기능과 파라미터 이름을 연결하며 하나라도 참인 값이면 기능을 활성화합니다.
실행 검증에 따라 제공 기능이 달라지면 `MethodOutput.provides`를 명시합니다.
거절한 결과는 기능을 제공하지 않습니다.

단순 조회에 인과·추론 기능을 선언하지 않습니다.
통계·ML 라이브러리는 의존성·제한된 추출·`MethodOutput(runtime=...)`의 버전 근거가 필요합니다.
선택 라이브러리가 없으면 해결 방법이 있는 오류를 반환하며 실행 중 자동 설치하지 않습니다.

## 검증과 호환성

독립적으로 계산한 정답·필수 역할 누락·잘못된 파라미터·빈 데이터·쿼리 한도·근거·해석 한계를 검사합니다.
계산은 엄격한 쿼리 fixture로, provider 동작은 실제 연동 테스트로 확인합니다.
Method의 출력을 자기 자신의 정답으로 쓰지 않습니다. 새 입력 타입은 편집 화면도 테스트합니다.

기존 Method로 충분하지 않은 이유, 필요한 grain·provider 기능, 지원하지 않는 가정·경고,
고정 버전 Recipe에 미치는 영향을 문서화합니다. 과거 Run은 그대로 두고 고정 버전은 검토 후 변경합니다.

```bash
.venv/bin/python -m pytest -q examples/methods
.venv/bin/python -m pytest -q tests/unit/test_method_contribution.py tests/unit/test_causal.py
make test
```

CEM은 조건 구성만 다른 사례·독립 계산한 가중치·공통 구간·유지율·표본 건수·겹치는 집단·잘못된 구간을 검사합니다.
원본 평균에는 선언된 표본 건수, 조회 가능한 공통 기본 키, 개별 단위마다 유한하고 누락되지 않은 결과가 필요합니다.
현재 hosted dbt metadata로는 이 경로를 확인할 수 없습니다. 연속형 결과의 유의성 추론은 지원하지 않습니다.

백분율 추론에는 선언된 건수 분자·분모, 같은 범위의 건수·단위 확인이 필요합니다.
값의 모양만으로 백분율 의미를 추측하지 않습니다. 맞춤 후 균형은 구간별 조건에 관한 것입니다.
조건의 측정 시점·표본 독립성·인과 식별은 별도 검토가 필요합니다.
[CEM 테스트](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_causal.py)를 참고하세요.

## 코드 참고

- [Python Method 프로젝트](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)와 [SDK 실행 테스트](https://github.com/haechangcho/decision-layer/blob/main/tests/support/methods/functions.py)
- [Method 기본 계약](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/base.py)·[Registry](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/registry.py)·[실행 context](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/context.py)
- [공통 모델](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/core/models.py)과 [계약 테스트](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_method_contribution.py)
- [테스트](../guides/development.md)와 [기여 절차](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)

## 기존 구현에서 전환

기존 class Method·bindings·등록·Recipe version은 유지됩니다. 단순 Method만 typed 함수로 옮기고 독립 full-spec fixture로 동일 계산을 확인한 후 새 version을 배포하세요. 추가 artifact·selection이 필요한 class는 유지해도 됩니다. 기존 Recipe는 검토 후 pin을 바꾸며 과거 Run을 다시 쓰지 않습니다. 서버 설치에는 core만 또는 필요한 extras를 선택하고, Cube model의 observation key/panel 변경과 API 재배포는 별도로 적용합니다. DB migration은 없습니다.

새 Python 작성자는 함수 인자를 이름 그대로 전달합니다. roles/parameters는 semantic 참조와 일반 값을 검증하기 위한 내부 구분입니다. `AnalysisDesign` 파싱은 기존 직렬화 Method 계약의 호환용으로만 유지하며 새 예제에서 사용하지 않습니다. ADR-084를 참고하세요.

## 탐색과 작성 기본값

`@method(name, version=...)`의 기본 해석은 `association`입니다. 타입은 signature, 설명은 docstring에서 가져오며 코드에서 목적을 추측하지 않습니다. `provides`는 선택 사항이지만 명시한 결과 계약은 Recipe와 목표 근거 검사에 계속 사용합니다. [검토 결과와 실행 가능한 탐색 예제](../guides/methods.md)를 참고하세요. `POST /methods:search`는 `MethodSearchRequest`의 `goal`과 선택적인 `names`를 받으며 분석 쿼리를 실행하지 않습니다.
