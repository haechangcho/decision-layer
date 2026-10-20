# Method API

함수를 등록할 때 필요한 인자와 옵션을 찾아보는 문서입니다. 전체 흐름은 [Python 함수 연결 예제](../tutorials/write-your-method)에서 볼 수 있습니다.

## `python_method`

```python
from decision_layer.methods import Column, DataInput, Scope, python_method

method = python_method(
    function,
    name="my_team.analysis",
    version="1.0.0",
    inputs={"data": DataInput(columns={...})},
)
```

| 인자 | 의미 |
|---|---|
| 첫 번째 인자 | 실행할 Python 함수 |
| `name`, `version` | Method 이름과 버전. 필수 |
| `inputs` | 데이터를 받을 함수 인자와 `DataInput`의 연결. 필수 |
| `output` | 반환 형태. 기본 `"auto"`, 또는 `"table"`, `"estimate"` |
| `requires_packages` | 필요한 패키지와 버전 범위. 예: `{"statsmodels": ">=0.14,<0.16"}` |
| `checks` | 조회한 데이터의 추가 검사 함수 목록 |
| `option_checks` | 데이터 조회 전에 실행할 계산 옵션 검사 함수 목록 |
| `adapt` | 함수 반환값을 공통 결과 형태로 바꾸는 선택적 함수 |
| `provides` | Recipe와 분석 목표에서 사용할 capability 이름 목록 |

함수의 일반 인자는 계산 옵션이 되며, 타입과 기본값에서 입력 조건을 추출합니다. `parameters`로 조건을 직접 지정할 수도 있습니다. 함수의 docstring은 Method 설명으로 사용합니다.

`requires_packages`는 설치 여부와 버전을 확인합니다. 실행 중 패키지를 설치하지는 않습니다.

## `DataInput`과 `Column`

`inputs`의 키는 DataFrame을 받는 함수 인자 이름입니다. 여러 DataFrame이 필요하면 각각 선언합니다.

```python
inputs={
    "data": DataInput(
        columns={
            "value": Column(source="measure", dtype="number"),
            "group": Column(source="dimension"),
        },
        minimum_rows=10,
    ),
}
```

| `Column` 옵션 | 의미 |
|---|---|
| `source` | `"measure"`, `"dimension"`, 또는 두 값을 담은 목록. 필수 |
| `dtype` | 필요한 자료형: `"number"`, `"string"`, `"boolean"`, `"time"`. 생략하면 제한하지 않음 |
| `multiple=True` | 여러 지표나 차원을 선택. 기본 `False` |
| `required=False` | 선택 입력으로 선언. 기본 `True` |
| `role="entity_key"` | 고객 ID나 주문 ID처럼 한 행을 구분하는 키 |
| `description` | 입력의 용도 설명 |

`entity_key`는 필수 차원 하나여야 하고 semantic layer에 개체 키로 정의되어 있어야 합니다. 한 DataInput에 하나만 선언합니다. 키를 선택했다고 통계적 독립성이 보장되는 것은 아닙니다.

선언한 열과 이름이 같은 함수 인자에는 DataFrame의 열 이름을 전달합니다. 여러 열은 `confounders_0`, `confounders_1`처럼 이름을 붙이고 목록으로 전달합니다. 실제 Cube 식별자는 실행할 때 `bindings`로 선택합니다.

| 자주 쓰는 `DataInput` 옵션 | 의미 |
|---|---|
| `minimum_rows` | 최소 행 수. 기본 `1` |
| `format` | 기본 `"dataframe"`. `"records"`는 행 dict 목록 |
| `time_granularity` | `"day"`, `"week"`, `"month"`, `"quarter"`, `"year"` 단위 조회 |
| `period_parameter` | 비교 기간을 받을 계산 옵션 이름 |
| `period_role="comparison"` | 별도로 선택한 비교 기간 조회 |
| `filters_parameter` | 추가 조회 조건을 받을 계산 옵션 이름 |

## 반환값

| 함수 반환값 | 처리 방법 |
|---|---|
| DataFrame, 행 dict 목록 | 기본 설정에서 표로 변환 |
| 숫자 | 기본 설정에서 추정값으로 변환 |
| dict | 기본 설정에서는 한 행의 표 |
| `{"value": 숫자, ...}` | `output="estimate"`로 지정하면 추정값과 상세 정보로 변환 |

`output="table"`과 `output="estimate"`는 반환 형태를 고정합니다. 다른 형태가 나오면 오류가 납니다. 지원하지 않는 외부 라이브러리의 결과 객체는 함수 안에서 변환하거나 `adapt`를 사용합니다.

## 검사와 오류

필수 입력, 자료형과 선언한 데이터 조건은 Decision Layer가 검사합니다. 모든 Method에 별도 오류 처리를 작성할 필요는 없습니다.

- `checks`는 데이터를 받은 뒤 계산 전에 실행합니다. 함수는 `DataInput` 이름으로 데이터를 받습니다.
- `option_checks`는 계산 옵션만 받아 조회 전에 실행합니다.
- 검사 함수가 `False`를 반환하거나 `ValueError` 또는 `AssertionError`를 발생시키면 검증 실패로 기록하고 계산을 멈춥니다. `None`이나 `True`는 통과입니다.
- 계산 함수 자체의 예외는 Python 오류로 전파됩니다. 프로그래밍 오류를 성공 결과로 바꾸지 않습니다.

## 로컬 세션

| API | 용도 |
|---|---|
| `session.register(method)` | 현재 세션에 Method 추가 |
| `session.list_methods()` | 등록된 manifest 목록 확인 |
| `session.find_methods(...)` | 입력 조건을 포함해 Method 검색 |
| `await session.run(name, bindings=..., params=..., scope=...)` | 로컬 실행과 결과 확인 |

`bindings`는 실제 semantic 식별자, `params`는 계산 옵션입니다. `Scope(date_range=(시작일, 종료일), time_dimension=날짜_식별자)`로 기간을 지정합니다.

반환된 `trial.result`에서 결과를, `trial.attempts`에서 조회 기록을 확인합니다. 이 결과는 서버에 자동 저장되지 않습니다. 서비스 등록은 [프로젝트에 등록하기](../guides/method-projects.md)를 참고하세요.

여러 조회를 직접 제어하는 고급 API는 [SDK 예제](https://github.com/haechangcho/decision-layer/blob/main/tests/support/methods/functions.py), 전체 인자는 [구현](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/python.py)에서 확인할 수 있습니다.
