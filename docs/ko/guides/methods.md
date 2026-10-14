# 첫 Method 작성, 실행, 테스트

일반 Python 함수 하나를 작성하고 명시적으로 등록합니다. 의미 정의, join, 권한은 semantic layer에 남습니다. 이 페이지의 코드는 구현된 API이며, 앞으로 구현할 의사 코드가 아닙니다. 기존 class 기반 Method도 계속 사용할 수 있습니다.

**내 Method를 직접 작성하고 수정해보려면** VS Code/Jupyter에서 `examples/methods/patterns/write_your_method.ko.ipynb`를 여세요. 준비된 시나리오 실행뿐 아니라 함수 작성 → 등록 → 입력 선택 → 결과 확인 → 코드 수정이 셀로 이어집니다. 영어 notebook과 코드는 동일하며, 마지막 선택적 연결 셀에서 같은 함수를 현재 Cube에 사용합니다.

## 1. 외부 연결 없이 시작

저장소 루트에서 실행하세요. 아래 첫 테스트는 Python 3.11+와 core 의존성으로 실행되고 통계 라이브러리가 필요한 사례는 건너뜁니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m examples.methods.patterns --case by_group
.venv/bin/python -m pytest -q examples/methods/patterns/test_patterns.py
```

## 2. 함수 작성

`Measure`, `Dimension`은 기존 semantic 객체의 참조를 받습니다. `ctx`가 기간과 필터, 권한, 제한을 적용합니다. 함수 signature에서 manifest가 생성되므로 역할 선언과 인자 매핑을 중복 작성하지 않습니다. 아래는 실제 테스트하는 소스입니다.

<<< @/../examples/methods/patterns/methods.py#group_metric

`@method`는 Method 이름과 버전을 지정합니다. `interpretation="association"`은
관측 데이터의 요약과 관계 분석을 뜻합니다. 그룹별 조회, 월별 추이, 회귀의 연관성
분석을 포함하며 인과효과를 주장하지 않습니다. 새 Method는 이 분류를 사용하고,
기존 `descriptive`, `associational` 값도 계속 지원합니다.

`Table.from_dataset(data)`는 행 데이터와 각 열의 semantic 정보를 함께 보존합니다.
월별 조회도 같은 `Table`을 반환합니다. 웹은 시간 정보를 사용해 추이 그래프를
표시하므로 별도의 반환 타입을 선택할 필요가 없습니다.

<<< @/../examples/methods/patterns/methods.py#series

주요 결과가 하나의 추정값과 분석 상세 정보라면 `Estimate`를 사용합니다.

### AI 요청과 Python 호출에서 입력이 채워지는 방식

요청 예: “2001년 2월 store 364의 판매액를 department별 상위 3개 보여줘.”

AI는 semantic layer에서 판매액 지표와 department 분류 기준을 찾아 다음 입력에 넣습니다.

- `metric`: 판매액 지표가 정의된 모델과 지표의 경로
- `group`: department가 정의된 모델과 분류 기준의 경로
- `limit`: 요청한 3. 생략하면 함수 기본값 사용
- `scope`: 2001년 2월, 날짜 기준, store 364 필터

예를 들어 `cube://journey/transaction/receipts`는 다음 항목을 가리킵니다.

- `cube://`: Cube semantic provider
- `journey`: 연결된 Cube 인스턴스의 이름
- `transaction`: Cube 모델 이름
- `receipts`: 그 모델에 정의된 지표 이름

Cube에 연결하면 catalog에서 이 경로를 확인해 `run(metric=...)`에 넣습니다. 이 경로는 DB 테이블이나 SQL 컬럼의 위치가 아닙니다. 다른 모델의 `cube://journey/product/department`도 `group`에 넣을 수 있으며, 연결 가능 여부와 join은 Cube가 판단합니다. 연습용 `cube://practice/observations/value`에서는 `practice`가 연습 연결 이름이고 `observations`와 `value`는 예제 catalog에 정의된 이름입니다.

Python에서는 `run(...)`에 `metric`, `group`, `limit`, `scope`를 직접 넣습니다. 실행할 때 입력은 이렇게 전달됩니다.

- `run(metric=...)`에 넣은 값은 Method 함수의 `metric`으로 전달됩니다. `group`, `limit`도 같은 방식입니다.
- `scope`의 기간과 필터는 `ctx`에 들어갑니다. `ctx.aggregate(...)`가 조회에 적용합니다.
- 데이터 연결, 권한, 실행 제한은 session에 설정되어 있으며 `ctx`가 조회할 때 사용합니다.

입력이 부족하거나 모호하면 다음과 같이 처리합니다.

- 요청한 지표나 기간이 불명확하면 AI가 사용자에게 질문합니다.
- 런타임이 `needs_input`을 반환하면 AI가 해당 질문을 전달합니다.
- 필수 Method 인자를 빠뜨리면 입력 오류가 발생합니다.

Method는 `ctx.aggregate(...)`로 정해진 기간과 필터, 권한, 제한에 따라 조회합니다.

Python 호출은 직접 실행하므로 대화를 진행하지 않습니다. AI는 서버에 등록된 Method의 입력 설명을 보고 MCP 호출을 준비합니다. Run을 만들 때 공통 조건을, 실행 단계에는 Method 인자를 전달하며 같은 실행 context와 registry를 사용합니다. 필수 타입 선언은 필수 입력을 뜻하며 자동 채팅 질문을 생성하지 않습니다. Method가 분석상 선택을 결정할 수 없으면 `NeedsInput`을 반환할 수 있고, 호출자는 답을 받아 유효한 입력으로 다시 실행해야 합니다. 기본값은 Method, Recipe가 정의한 범위에서 사용합니다. 연결 인증과 권한 규칙은 설정된 실행 환경에서 제공합니다.


## 3. 등록하고 실행, 정답 확인

아래 코드는 notebook의 셀 또는 async 함수 안에서 실행합니다. `FixtureProvider`는 Method가 만든 요청을 그대로 복사하지 않고 독립적으로 작성한 전체 `DatasetSpec`과 비교합니다. 값뿐 아니라 조회 조건이 틀려도 실패합니다.

```python
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from examples.methods.patterns.methods import group_metric
from examples.methods.patterns.scenarios import scenarios, M, GROUP, DATE, FEB

scenario = next(s for s in scenarios() if s.name == "by_group")
provider = scenario.provider()
session = await MethodSession.fixture(provider)
session.register(group_metric)
trial = await session.run(
    group_metric,
    metric=M, group=GROUP,
    scope=Scope(FEB, DATE), limit=3,
)
assert [r["metric"] for r in trial.result.primary.data] == [30, 20, 10]
provider.assert_consumed()
print(trial.queries)
print([(a.label, a.status) for a in trial.attempts])
session.close()
```

## 4. 실제 semantic source 연결

```python
import os
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, Filter
from decision_layer.semantic.credentials import RequestCredentials

session = await MethodSession.cube(
    os.environ["CUBE_API_URL"], RequestCredentials(os.environ["CUBE_TOKEN"]),
    instance="journey",
)
metrics = session.catalog.search(kind="measure", text="sales")
metric = metrics[0].ref  # Inspect titles/definitions before choosing.
print(session.object(metric))
print(session.catalog.relations(metric))  # declared or unknown, not a join guarantee
print(session.catalog.search(kind="dimension", text="department", compatible_with=metric))
print(session.catalog.search(kind="time_dimension"))
# Copy actual references from this caller-visible catalog into the invocation.
# session.register(group_metric)
# trial = await session.run(group_metric, metric=metric,
#     group=selected_dimension,
#     scope=Scope(selected_period, selected_time),
#     filters=[Filter(member=selected_filter_dimension, operator="equals", values=[selected_value])])
session.close()
```

탐색 API는 접근 가능한 객체만 반환합니다. `compatible_with`는 참조를 확인하는 탐색 힌트이며 모르는 join을 임의로 제외하거나 가능하다고 보증하지 않습니다. 실제 조합은 provider가 검증합니다.

## 5. 수정, 디버깅, 공유

함수를 수정한 뒤 `session.register(group_metric, replace=True)`로 재등록합니다. 일반 breakpoint를 사용하고 `session.last_trial.attempts`에서 성공, 실패한 요청과 label을 확인합니다. 직접 실행은 호출자 프로세스에서 동작하며 저장된 Run이 아닙니다. `session.preview(recipe, step_index=..., scope=...)`는 같은 RunEngine으로 새 Recipe prefix를 실행합니다.

배포하려면 검토된 모듈을 서버 환경에 설치하고 서버 bootstrap에서 등록하세요. import만으로 자동 등록하지 않으며 Web에서 Python을 업로드하지 않습니다. 기존 Method를 조직의 조사 절차로 조합할 때는 Recipe를 작성합니다.

다음: [작성 패턴](method-patterns.md), [직접 테스트 시나리오](method-scenarios.md), [고급 분석](statistical-methods.md), [내부 계약](../reference/method-contract.md).

## 등록된 Method 확인

목적은 docstring 한 곳에 적습니다. `interpretation`을 생략하면 `association`입니다. `session.find_methods()`는 데이터를 조회하지 않고 등록된 계약과 실행 조건을 확인합니다. Python, REST, 웹, MCP의 공통 흐름과 모호한 질문, 호환성은 [Method 작성과 AI 탐색](method-discovery.md)을 참고하세요.

## MVP 기본 기능과 선택 확장

처음 제품에서는 조회 Method 세 개와 DoWhy 분석 두 개를 제공합니다.

| Method | 용도 |
| --- | --- |
| `query.aggregate` | 정의된 지표 값 조회 |
| `query.trend` | 기간별 추이와 기간 비교 |
| `query.drilldown` | 그룹별 값과 변화를 나누고 특정 항목을 이어서 조사 |
| `stats.binary_matching` | DoWhy로 처치 집단을 매칭해 비교 (ATT) |
| `stats.regression_adjustment` | DoWhy OLS로 처치 1단위 증가당 변화량 또는 특정 대비 추정 |

Recipe는 이 Method들을 재사용할 조사 절차로 조합합니다. 집단 비교, 개체 분석,
다른 통계 분석은 선택 기능입니다. DoWhy 결과의 인과 가정은 검증되지 않았습니다. 기존 Recipe의 명시적인 참조는 원래 실행 계약을 유지합니다.

필요한 기능은 검토한 서버 시작 코드에서 기존 Registry로 등록합니다.

```python
from decision_layer.methods import registry
from decision_layer.methods.peer_comparison import PeerComparison

registry.register(PeerComparison())
```

OLS는 문서에 안내한 stats 의존성을 설치한 뒤 등록합니다.

```python
from decision_layer.methods import registry
from decision_layer.methods.advanced import ols

registry.register(ols)
```

등록하면 웹, REST, MCP가 같은 계약을 사용합니다. 호환 구현이 이미 있는 로컬
session에서는 `session.register(ols, replace=True)`를 사용합니다. 재시작 후에도
적용되도록 검토한 서버 시작 코드에 등록을 둡니다. 일반 Python 확장이며 화면에서
설치하는 플러그인 기능은 아닙니다. 마켓과 웹 플러그인 관리는 후속 범위입니다.
기본 목록은 접근 권한 제한을 뜻하지 않습니다. 기존 Recipe의 명시적인 참조는
정상적인 권한과 검증을 적용해 계속 실행됩니다.
