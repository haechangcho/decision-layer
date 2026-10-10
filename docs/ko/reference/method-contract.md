# Method 계약

입력·출력·편집 화면 동작을 선언할 때 참고하는 문서입니다.
실행 가능한 예제부터 시작하려면 [첫 Method 개발](../guides/methods.md)을 보세요.

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

- [첫 Method](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/first_method)와 [여러 쿼리를 조합하는 Peer Comparison](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/peer_comparison)
- [Method 기본 계약](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/base.py)·[Registry](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/registry.py)·[실행 context](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/context.py)
- [공통 모델](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/core/models.py)과 [계약 테스트](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_method_contribution.py)
- [테스트](../guides/testing.md)와 [기여 절차](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)
