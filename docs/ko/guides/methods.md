# Python Method 만들기

일반 Python 함수를 작성하고, 어떤 데이터를 받을지 선언합니다.
Decision Layer가 선택한 데이터를 조회해 함수에 전달하고, 서버 실행 결과는 Run에 기록합니다.

처음이라면 [Method 작성 노트북](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/write_your_method.ko.ipynb)을 실행해 보세요.
순위 계산과 OLS를 작성하고, 준비된 데이터로 등록과 실행을 직접 해볼 수 있습니다.

## 함수와 입력 정의하기

다음 함수는 `value` 열의 순위를 계산합니다. `DataInput`에는 지표와 그룹 기준이
필요하다고 선언합니다. 실제 매출 지표와 상품 차원은 실행할 때 선택합니다.

```python
from decision_layer.methods import Column, DataInput, python_method


def rank_values(data, descending=True):
    """Rank groups by the selected metric, retaining ties."""
    return data[["group", "value"]].assign(
        rank=data["value"].rank(method="min", ascending=not descending)
    )


METHOD = python_method(
    rank_values,
    name="my_team.rank",
    version="1.0.0",
    inputs={
        "data": DataInput(columns={
            "value": Column(source="measure"),
            "group": Column(source="dimension"),
        }),
    },
)
```

- `python_method`: 함수, 이름, 버전과 입력 조건을 묶습니다.
- `Column`: 조회할 열의 역할입니다. 같은 이름의 함수 인자가 있으면 조회한 열 이름을 전달합니다.
- `descending`: 함수 기본값에서 계산 옵션으로 추출합니다.
- `METHOD`: 프로젝트 파일을 읽는 로더가 찾는 객체입니다.

표, 숫자, dict를 반환할 수 있습니다. 기본 `output="auto"`가 표와 추정값을 구분하며,
반환 형태를 고정하려면 `output="table"` 또는 `output="estimate"`를 지정합니다.

## 분석에 맞는 입력 조건

| 선언 | 의미 |
| --- | --- |
| `Column(source="measure")` | 지표 선택 |
| `Column(source="dimension")` | 차원 선택 |
| `Column(source=["measure", "dimension"])` | 지표와 차원 모두 허용 |
| `Column(source="dimension", role="entity_key")` | 고객 ID나 주문 ID처럼 한 행을 구분하는 키 |
| `Column(source="measure", dtype="number")` | 숫자형만 허용 |
| `Column(source="dimension", multiple=True)` | 여러 변수 선택 |
| `DataInput(..., minimum_rows=10)` | 조회 결과가 최소 10행이어야 함 |

입력 누락, 종류 불일치와 선언한 데이터 조건은 공통 코드에서 확인합니다.
분석 고유의 가정은 작성자가 검토합니다. 함수가 계산을 계속할 수 없으면 일반 Python
예외를 사용하고, 실패를 검증 결과로 기록하려면 `checks=[검사함수]`를 지정합니다.

## 등록한 뒤 사용하기

파일로 저장하는 구조, CLI 검사, 관리자 화면과 AI 연결은
[프로젝트에서 사용하기](method-projects.md)에서 이어집니다.

AI는 `list_methods`와 `find_methods`로 등록된 Method를 찾고 `describe_method`로
입력 조건을 확인합니다. 지표와 차원은 semantic catalog에서 선택하며,
의미나 기간이 모호하면 사용자에게 확인합니다.

이미 있는 분석을 재사용할 때는 새 함수를 만들기 전에 [Recipe](recipes.md)로 조합할 수 있는지 확인하세요.
직접 여러 조회를 제어해야 하는 고급 API는 [Method 계약](../reference/method-contract.md)을 참고하세요.
