# Method 작성과 테스트

[Method 프로젝트](method-projects.md)에서 시작합니다. Python 계산 함수와 Skill
Markdown을 같은 폴더에서 관리하고 CLI 검사·로컬 실행·API 시작이 같은 파일을
읽습니다. 완성 예제는 `examples/methods/project`에 있습니다.

```sh
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer new skill metric_review
decision-layer check
decision-layer list
decision-layer serve --reload
```

`<이름>/methods/<정의>/method.py`는 `python_method`로 만든 `METHOD` 객체 하나를
내보냅니다. Skill은 자체 폴더에 `SKILL.md`를 둡니다. `list`는 원본 경로를 함께
보여주므로 어디서 등록됐는지 확인할 수 있습니다. 프로젝트 표시는
`decision-layer.yaml`이며 운영에서는 `DL_PROJECT_DIR`로 이 폴더를 지정합니다.
기존 모듈의 `METHODS` 등록도 계속 지원합니다.

새 계산은 일반 Python 함수, 기록된 조회를 안내하는 지침은 Skill, 기존 Method의
재사용 가능한 실행 순서는 Recipe로 만듭니다. `DataInput(columns={...})`에
`Column(source="measure")`처럼 필요한 열을 선언합니다. 지표와 차원을 모두
허용하면 `source=["measure", "dimension"]`으로 명시합니다. 같은 이름의 함수
인자에는 조회한 열 이름이 자동으로 전달됩니다. 분석 단위의 키도
`"entity_id": Column(source="dimension", role="entity_key")`처럼 선언합니다.
실행할 때는 `bindings={"entity_id": "cube://...", ...}`로 실제 식별자를 연결합니다.
다른 변수와 등록 및 실행 방식이 같습니다. 기존 measures/dimensions, RoleSpec, column_args 형식도 계속 지원합니다.

`docs/tutorials/methods/write_your_method.ko.ipynb`에서 순위 함수와 OLS 함수를
작성하고 로컬에서 등록 및 실행할 수 있습니다. 프로젝트 저장, 관리자 화면, MCP 연결과
실제 Cube 실행은 [만든 Method 사용하기](./method-deployment.md)에서 이어집니다.
로컬 trial은 코드를 업로드하거나 Run을 저장하지 않습니다. 서버 실행은 같은 입력
조건으로 실행하고 Run에 근거를 남깁니다.

## 고급 경로: 소스 조회를 직접 제어해야 할 때

아래 예제는 source-aware 고급 API입니다. 일반 계산 함수에 이 형식을 강제하지 않습니다.

## 1. 외부 연결 없이 시작

저장소 루트에서 실행하세요. 아래 첫 테스트는 Python 3.11+와 core 의존성으로 실행되고 통계 라이브러리가 필요한 사례는 건너뜁니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m examples.methods.scenarios --case by_group
.venv/bin/python -m pytest -q tests/examples/test_scenarios.py
```

## 2. 함수 작성

`Measure`, `Dimension`은 기존 semantic 객체의 참조를 받습니다. `ctx`가 기간과 필터, 권한, 제한을 적용합니다. 함수 signature에서 manifest가 생성되므로 역할 선언과 인자 매핑을 중복 작성하지 않습니다. 아래는 실제 테스트하는 소스입니다.

<<< @/../examples/methods/scenarios/methods.py#group_metric

`@method`는 Method 이름과 버전을 지정합니다. `interpretation="association"`은
관측 데이터의 요약과 관계 분석을 뜻합니다. 그룹별 조회, 월별 추이, 회귀의 연관성
분석을 포함하며 인과효과를 주장하지 않습니다. 새 Method는 이 분류를 사용하고,
기존 `descriptive`, `associational` 값도 계속 지원합니다.

`Table.from_dataset(data)`는 행 데이터와 각 열의 semantic 정보를 함께 보존합니다.
월별 조회도 같은 `Table`을 반환합니다. 웹은 시간 정보를 사용해 추이 그래프를
표시하므로 별도의 반환 타입을 선택할 필요가 없습니다.

<<< @/../examples/methods/scenarios/methods.py#series

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
from examples.methods.scenarios.methods import group_metric
from examples.methods.scenarios.scenarios import scenarios, M, GROUP, DATE, FEB

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
| `analysis.metric_lookup` (Skill) | 정의된 지표 값 조회 |
| `analysis.trend` (Skill) | 기간별 추이와 기간 비교 |
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

## 조회 Skill 연결 (ADR-098/103)

노트북 마지막 절은 `analysis.drilldown` → `analysis.peer_comparison` 두 단계입니다.
AI가 `run_skill_query`로 쿼리를 제출하면 공통 실행기가 기간·필터·권한·한도를
검사하고 실제 조회·실패를 기록합니다. `finish_skill_step`에서 실제 행을 선택합니다.
가구 회귀 단계를 자동으로 덧붙이지 않습니다. 별도로 등록한 Python 계산에 선택
근거와 필터를 전달하는 DataInput 경로는 유지하며 앞 절의 함수 예제로 배웁니다.

Web Run에서 지침·쿼리·결과·오류를 확인합니다. 지침을 읽었다고 동료 집단의
타당성이 검증되는 것은 아닙니다. Web은 외부 AI 실행을 기다리며 노트북 실습은
실제 Claude 실험이 아닌 fixture 재현입니다.

## 조회 Skill과 계산 분리 (ADR-099/103)

기본 지표 조회·추이는 한국어 `analysis.metric_lookup`, `analysis.trend` Skill입니다.
공통 실행기에 실제 조회와 결과를 기록합니다. 기간 변화·시계열 진단·예제 가구 회귀는
새 Method 목록에서 제외했습니다. 필요한 계산이 제공되지 않으면 해당 주장을 중단하며,
Skill 문장이나 AI의 임의 계산을 검증 근거로 쓰지 않습니다.

드릴다운·추이 지침은 1.1.0입니다. 과거 버전을 고정한 Recipe와 Run은 유지합니다.
현재 `campaign_recipe()` 1.1.0은 드릴다운 → peer 조회의 두 단계입니다.
과거 세 단계 실험은 `legacy_campaign_recipe()`로 명시적으로 재현합니다.

## Web에서 코드와 Skill 수정 (ADR-100)

Method 상세에서 Python 진입·보조 코드 또는 서식 있는 Skill을 읽습니다. 수정은
현재 버전에서 새 초안을 만들고, 저장 → 구문·등록 검사 → 검토 확인 → 새 버전 게시
순서입니다. 검사 통과는 실제 데이터나 분석 품질의 검증이 아닙니다. Python 검사와
게시는 신뢰한 운영자 코드를 실행하며, Method 게시 권한이 별도로 필요합니다.

일반 설치는 `DL_METHOD_ASSETS_DIR`와 `DL_ALLOW_METHOD_EDITING=true`로 운영자가
활성화합니다. `DL_METHOD_EDITORS`/`DL_METHOD_PUBLISHERS`는 Recipe 역할과 별개입니다.
현재 local/demo만 지원하며 공유 환경의 임의 코드 sandbox는 없습니다. 예제 Compose는
기존 data 볼륨의 `/data/method-assets`를 사용합니다. UI 게시 파일과 원래 Git 모듈은
별도 버전 원본이며, Git 반영은 명시적으로 검토·이관합니다.

새 Run은 선택된 코드와 해시를 저장합니다. 과거 Run에 코드가 없으면 현재 코드로
대신 표시하지 않습니다. 이전에 등록된 버전은 고정 Recipe에서 계속 선택할 수 있으며,
설치되지 않은 버전은 거부합니다. 외부 라이브러리 전체와 환경 재현은 별도 관리합니다.

### Web의 작성 코드와 전체 소스

새 계산은 일반 함수와 `python_method`/`DataInput` 등록으로 시작합니다. Web의
**Python 작성 코드**에는 선택한 분석의 함수·필요한 검사·등록만 표시하고 수정
초안도 여기서 시작합니다. 같은 파일의 다른 분석·Recipe·테스트 준비 코드를
작성자에게 복사하도록 요구하지 않습니다. 실제 원본과 해시는 **전체 소스와 실행
근거 보기**에서 확인합니다. 동적 초기화로 안전하게 분리할 수 없으면 원본을 유지합니다.

호환용으로 남긴 `stats.series_diagnostics` 1.1.0은 계산을 일반 pandas 함수로 분리한 과거 구현입니다.
입력은 `period`, `metric`, `value` 열, 출력은 `metric`, `from`, `to`, `before`,
`after`, `change` 열입니다. 이 특정 기본 분석은 `SeriesDiagnostics(함수, version=...)`
한 줄로 기존 조회·기간 검사·최신성 검사·결과 어댑터에 연결합니다. 이것을 새 분석
전체에 요구하는 틀로 사용하지 않습니다. 일반적인 새 분석에는 위의 DataInput 경로를
사용하세요. 이전 1.0.0은 고정된 Recipe에서 계속 실행할 수 있습니다.

### 상세 화면에서 바로 편집하기

지침 위의 **Skill.md 편집**, 코드 위의 **Python 편집**을 누르면 읽던 자리가 편집기로
전환됩니다. 줄 번호·구문 색상·찾기/바꾸기·실행 취소를 지원하며 **미리보기**와
**변경 비교**를 오가도 작성 내용을 유지합니다. ⌘/Ctrl+S는 초안 저장입니다.
**구문·등록 검사**는 필요한 초안 저장을 먼저 처리합니다. Python은 신뢰한 코드라는
검토 확인이 있어야 검사할 수 있습니다. 검사 통과와 검토 확인 후 **v… 게시**를 누릅니다.
게시 전에는 실행 버전이 바뀌지 않으며, 고정된 Recipe와 과거 Run도 바뀌지 않습니다.

읽기로 돌아가도 편집 내용은 같은 화면에 유지됩니다. 다른 링크로 이동할 때 미저장
내용이 있으면 저장·계속 편집·버리기를 선택합니다. 새로고침/창 닫기는 브라우저의
미저장 경고를 사용합니다. 서버 초안 저장 후에는 페이지를 새로 열어도 이어서 편집할
수 있습니다. 저장 중 새로 입력한 내용은 미저장 상태로 남습니다. 서버 초안 충돌은
작성 내용을 유지하고 서버 내용과 비교한 뒤, 사용할 기준을 명시적으로 선택합니다.
