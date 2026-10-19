# 개발자와 AI가 이해할 수 있는 Method 만들기

[첫 Method](methods.md)를 작성한 뒤 등록된 설명과 입력을 확인합니다.
아래 API는 구현하고 실행 테스트한 기능입니다. 자연어 이해는 AI 클라이언트의
역할이며, 이 기능이 Method를 자동으로 선택하지는 않습니다.

## 무엇이 바뀌었나

기존에는 docstring이 없는 함수가 이름만으로 소개됐습니다. MCP는 이름과 입력
요약을 제공하면서 요인 관계에는 CEM, 변화 질문에는 정해진 순서를 사용하도록
지시했습니다. 실제 후보를 비교해서 정한 규칙은 아니었습니다.
`provides`에 목록 대신 문자열을 넣으면 글자마다 분리되는 문제도 있었습니다.

기존 API가 docstring에서 설명을, signature에서 입력과 반환 계약을 생성하는
방식은 유지합니다. 관측 수준 해석의 기본값은 이제 `association`입니다. 예제는 목적을 docstring 한 곳에
적습니다. 설명이 없는 기존 함수도 실행되지만 탐색 결과에
`description_available=false`가 표시됩니다. docstring은 작성자의 설명이며,
코드가 그 설명대로 동작한다는 증명은 아닙니다.

`find_methods`는 실행과 같은 입력 검사로 타입, provider 기능, 설치된 라이브러리
버전을 확인합니다. 후보, 제외 이유, 등록된 결과 계약 이름을 반환합니다.
데이터를 조회하거나 첫 후보를 자동 선택하지 않습니다. MCP에 있던 고정 분석
순서는 제거했습니다. 조직의 조사 순서는 Recipe에 둡니다.

## 작성 코드 비교

기존 코드는 관측 수준 해석을 명시해야 했지만 목적 설명은 없었습니다.

```python
@method("example.group_metric", version="1.0.0", interpretation="association")
async def group_metric(ctx, *, metric: Measure, group: Dimension,
                       limit: int = 5) -> Table:
    data = await ctx.aggregate(measures={"metric": metric}, dimensions={"group": group},
                               order=[(metric, "desc")], limit=limit)
    return Table.from_dataset(data)
```

현재 실행 가능한 구현은 입력 범위를 제한하고 목적을 한 번 설명합니다.

<<< @/../examples/methods/scenarios/methods.py#group_metric

이 로컬 Method에는 별도 description, 입력 스키마, 출력 스키마, 검색 태그나
capability 목록이 필요하지 않습니다. 타입은 입력의 종류를 설명합니다.
measure 타입에 맞더라도 질문에서 원하는 결과 지표가 아닐 수 있습니다.

## 등록, 확인, 실행, 테스트

저장소 루트에서 전체 Python 예제를 실행합니다.

```bash
.venv/bin/python -m examples.methods.scenarios.discovery
.venv/bin/python -m pytest tests/unit/test_method_discovery.py
```

예제는 같은 `group_metric` 구현을 등록하고 설명을 확인한 뒤, 정해진 조회를
검사하는 fixture로 A=30, B=20, C=10을 반환합니다. 탐색은 쿼리를 사용하지 않습니다.
작성 실습 노트북에서도 방금 만든 Method를 아래처럼 확인합니다.

```python
method_choices = group_session.find_methods()
```

`MethodSession`은 로컬 개발용입니다. 실제 서비스에서는 검토한 Python 코드를
설치하고 서버 시작 시 등록합니다. MCP는 서버에 이름과 입력을 보냅니다.
질문마다 Python 코드를 업로드하거나 함수를 등록하지 않습니다.

분석 목적을 명시해서 확인할 때는 기존 `AnalysisGoal` 계약을 사용합니다.

```python
from decision_layer.core.models import AnalysisGoal

report = session.find_methods(goal=AnalysisGoal(
    id="lookup", description="Show the requested measure by group",
    semantic_refs=[M, GROUP], required_capabilities=["metric_lookup"],
    interpretation="association",
))
```

이 코드는 `examples/methods/scenarios/discovery.py`의 session과 참조를 사용합니다.
`metric_lookup`은 등록된 지표 조회 계약에서 가져온 이름입니다. 지원하지 않는
질문에 태그를 지어 넣거나, 후보가 나오게 하려고 태그를 바꾸면 안 됩니다.
빈 목록은 분석 목적에 관한 계약을 주장하지 않습니다.

REST는 같은 요청을 `POST /methods:search`의 `{"goal": ...}`로 받습니다.
MCP의 `find_methods(goal=...)`도 이 API를 호출하며 설정된 Method 목록으로
제한합니다. 웹 Method 상세 화면의 실행 조건 확인도
`{"names": [method_name]}`으로 같은 API를 호출합니다. 실행은 기존 Registry와
RunEngine을 그대로 사용합니다. 탐색 결과가 실행 권한이나 쿼리 예산을 부여하지 않습니다.

## 어떤 설정이 필요한가

| 정보 | 판단과 이유 | 생략하면 |
| --- | --- | --- |
| 이름과 버전 | 유지: 등록, Recipe 참조, provenance에 필요 | 필수 |
| 입력 타입과 기본값 | signature에서 생성하고 공통 Registry로 검사 | 필수 입력 누락은 조회 전에 오류 |
| 설명 | docstring 한 곳에 작성. 코드 내용에서 분석 목적을 추측하지 않음 | 기존 이름 대체를 유지하고 설명 부재를 표시 |
| `interpretation` | 기본값 `association`. 강한 해석은 명시와 분석 검증이 필요 | 관측 수준이며 인과 식별을 뜻하지 않음 |
| `provides` | 재사용할 **결과 계약**이 있을 때만 유지. 검색 키워드가 아님 | 빈 목록. `Table`에서 분석 능력을 추론하지 않음 |
| `provides_when` | 비교 옵션 등에 따라 결과가 달라지는 고급 class 계약에 유지 | 조건 없는 결과 계약만 적용 |
| `requires_packages` | 조회 전 버전 검사와 provenance에 필요. 잘못된 버전 문법은 함수 정의 시 거절 | 선언된 의존성 사전 검사 없음 |
| `requires_period` | 날짜 없이 수행할 수 없는 분석에 유지. 공통 기간 정책은 별도로 적용 | False. Method 고유의 기간 요구 없음 |
| `kind`, `execution` | 메타데이터와 기존 호환성을 위해 유지. 분석 목적이나 계산 격리의 근거로 사용하지 않음 | 기존 `query` / `semantic_pushdown` 메타데이터 기본값 |
| Provider 요구 기능 | `Entity` 입력에서 entity 조회 요구를 생성. 고급 class 선언 유지 | 추가 요구 기능 없음 |
| 편집기 이름, 그룹, 입력 출처 정책 | 기존 Recipe 편집과 동적 입력에 사용. 간단한 작성 경로에는 노출하지 않음 | 공통 입력 UI |
| Selection 출력 이름 | Recipe 단계 사이의 타입 있는 참조에 필요. 선언한 출력과 일치하는지 검사 | 선택 결과 없음 |
| 기존 `AnalysisDesign`, `TimeSeries`, 이전 해석 값 | 호환성 유지. 새 튜토리얼의 필수 개념에서 제외 | 일반 입력, Table/Estimate, association 사용 |

`provides`는 Recipe 탐색과 결과 근거 검사에서 정확한 값을 사용하므로 제거하지
않았습니다. 반환 타입이나 임의의 Python 조회 코드에서 자동 생성하지도 않습니다.
새 함수 선언에서는 문장, 빈 이름, 중복 이름, 목록 대신 문자열을 거절합니다.
사용자 정의 이름은 계속 허용하며, 작성자가 결과의 의미를 설명하고 테스트해야 합니다.
탐색 결과는 실제 설치된 이름과 Method를 `capabilities`에 제공하고 알 수 없는 요청
이름을 따로 반환합니다. 별도의 거대한 분류 체계 없이 확장과 기존 계약을 유지합니다.
문법 검사는 그럴듯하지만 의미가 틀린 선언까지 찾아내지 못합니다.

비슷한 문제도 수정했습니다. `int | str | None` 같은 optional union이 한 타입만
지원하는 것처럼 조용히 표시되지 않고 정의 시 거절됩니다. 비공개 객체는 탐색뿐
아니라 실행 컨텍스트에서도 거절합니다.

## Method를 선택하는 흐름

Recipe가 있으면 semantic 객체와 목표를 확인하고 `find_recipes`로 후보를 찾습니다.
절차, 고정 설정, 목표 지원 범위를 검토한 뒤 적합한 Recipe를 실행합니다.
기존 선택과 제외 기록, Recipe의 허용 Method 제한은 유지합니다.
탐색 결과가 Recipe의 허용 목록을 늘리지는 않습니다.

맞는 Recipe가 없으면 `find_methods`의 설명과 해석 범위를 비교합니다.
원하는 변수 역할과 비교를 확인한 뒤 공통 실행 입력을 넣습니다.
여러 후보가 서로 다른 질문에 답한다면 질문을 구체화합니다.
맞는 후보가 없으면 그 부분을 지원하지 못한다고 설명하고 더 쉬운 질문으로 바꾸지 않습니다.

시스템은 선언된 결과 계약, 해석 범위, 공개된 입력 타입, provider 기능과 설치
버전을 검사합니다. 후보 입력 경로는 목표에 포함된 참조 중 타입에 맞는 값이며,
**자동으로 정한 함수 인자가 아닙니다**. 기간, 실제 값, 조인, grain, 추출 제한,
분석 진단은 실행 시 확인합니다. 설명과 질문의 적합성, 교란변수 선택, 식별 가정은
도메인 판단이 필요합니다. 도구는 이를 증명했다고 표시하지 않습니다.

## 검증 시나리오와 한계

| 질문 상황 | 실행한 결정적 테스트 | 사람이나 AI가 판단할 부분 |
| --- | --- | --- |
| 지표를 그룹별로 보기 | `metric_lookup`으로 aggregate 후보와 타입에 맞는 참조 반환 | 지표와 그룹의 의미가 맞는지 |
| “이것 좀 분석해줘” | 결과 계약 제한이 없으면 여러 후보 유지 | 원하는 결과나 비교 질문 |
| 여러 방법이 가능한 질문 | 후보 목록 유지. 점수로 자동 선택하지 않음 | 추정 대상, 가정, 목적 비교 |
| 다음 달 매출 예측 | 미등록 예측 계약은 후보 없음과 알 수 없는 요구 이름 반환 | 지원 범위 설명. 단순 조회로 바꾸지 않음 |
| 인과 질문에 association Method만 지정 | 해석 범위 불일치로 제외 | 인과 식별에는 여전히 근거 필요 |
| 라이브러리 또는 entity 조회 미지원 | 조회 전에 구체적 제외 이유 반환 | 검토된 환경 준비 또는 적합한 지원 방법 선택 |
| 숨겨진 semantic 입력 | 탐색과 실행에서 같은 접근 오류. 데이터 조회 없음 | Provider를 통한 접근 권한 확보 |
| 비교 옵션이 있어야 제공되는 결과 | `conditional_capabilities`에 필요한 설정 반환 | 비교 값 지정. 실제 결과 계약은 실행 시 결정 |

확인한 개발 환경에서 실행 예제는 기본 Method 다섯 개와 작성한 예제 한 개를 목록에 포함했고, 목표 없이 사용 가능한
후보 6개, `metric_lookup`을 명시했을 때 1개를 반환했습니다. 구조적 후보 축소를
측정한 것이며 모델 정확도가 아닙니다. 설치된 패키지에 따라 수는 달라질 수 있습니다.
테스트는 이미 해석한 목표를 넣습니다. 이번 변경에서 실제 LLM이나 Databricks로
선택 정확도를 평가하지 않았습니다. 그룹별 fixture는 조회 구조와 결과 값을 확인하며,
실제 warehouse 조인이나 인과적 참값을 검증하지 않습니다.

## 호환성과 후속 검증

기존 Method ID와 버전, Recipe의 고정 버전, 결과 계약, 과거 Run 스냅샷은 바꾸지
않습니다. 이전 해석 값을 명시한 코드는 그대로 동작합니다. 새 기본값은
`interpretation`을 생략한 새 함수에만 적용됩니다. 잘못된 새 함수 선언은 일찍
거절하며 저장된 근거를 바꾸는 대신 선언을 수정합니다. 탐색 API는 추가 기능입니다.

Python과 REST 응답 일치, MCP 허용 목록 전달, 웹 실행 조건 확인, 비공개 입력,
정상 실행과 쿼리 기록을 테스트합니다. 실행을 공유하므로 기존 권한, scope,
예산, Recipe, provenance 테스트도 함께 적용합니다.

**미구현:** 자연어 의미의 진위 검증, 자동 Method 선택기, 학습 기반 순위,
모델과 무관한 선택 보장. 후속 평가는 같은 정상 질문, 모호한 질문, 미지원 질문을
각 AI 클라이언트에 넣어 선택한 Method, 추가 질문, 잘못된 지원 주장을 기록해야 합니다.
그 결과가 있어야 실제 선택 정확도가 좋아졌다고 말할 수 있습니다.
