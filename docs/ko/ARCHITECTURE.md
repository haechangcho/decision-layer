# 아키텍처

Provider, 실행 엔진, 인터페이스를 수정할 때 참고하는 문서입니다.
기본 흐름은 [Method 이해하기](guides/methods.md)에서 살펴볼 수 있습니다.

Decision Layer는 시맨틱 참조, 검토된 Method, 재사용 가능한 Recipe를 실행하고 근거를 기록합니다.
웹·REST·Python·MCP는 같은 계약과 실행 규칙을 사용합니다.
제품 방향은 저장소의 [제품 맥락](https://github.com/haechangcho/decision-layer/blob/main/docs/PRODUCT_CONTEXT.md),
상세 정책과 변경 이유는 [설계 결정](https://github.com/haechangcho/decision-layer/blob/main/docs/DECISIONS.md)에 있습니다.

## 코드 위치

| 책임 | 위치 |
| --- | --- |
| 공통 타입·ID | `src/decision_layer/core/` |
| Method 구현·작성 API | `src/decision_layer/methods/` |
| 로컬 Method 개발 | `src/decision_layer/dev.py` |
| 프로젝트 로딩·CLI | `src/decision_layer/project.py`, `src/decision_layer/cli.py` |
| 쿼리 fixture | `src/decision_layer/testing.py` |
| 시맨틱 계약·Cube adapter (과거 dbt 코드 보존) | `src/decision_layer/semantic/` |
| 연결 설정·인증 정보 저장 | `src/decision_layer/sources/` |
| Recipe 검증·편집·등록 | `src/decision_layer/recipes/` |
| Run 실행·작업·근거·저장 | `src/decision_layer/runs/` |
| HTTP 조립·리소스 라우트 | `src/decision_layer/api/` |
| MCP adapter | `src/decision_layer/mcp/` |
| 웹 페이지 | `web/app/` |
| Recipe·Run UI | `web/features/recipes/`, `web/features/runs/` |
| 공통 웹 입력·결과 UI | `web/components/` |
| 테스트 공용 provider·factory | `tests/support/` |
| 실행 가능한 기여 예제 | `examples/methods/` |

## 실행 흐름

```text
웹 / REST / Python / MCP
        ↓
실행 명세 또는 Recipe
        ↓
RunEngine: 범위·권한·선택·정책·근거
        ↓
MethodRegistry: 입력 기본값·연결 검사·출력 계약
        ↓
Method.run(ExecutionContext, bindings, params)
        ↓
ctx.aggregate/entities → ExecutionContext.dataset(DatasetSpec)
        ↓
시맨틱 provider → 제한된 Dataset
        ↓
MethodOutput → 검증 → Result → Run 근거
```

로컬 `MethodSession.run()`은 같은 Registry와 context를 호출자의 이벤트 루프에서 실행합니다.
Breakpoint를 사용할 수 있고 실행마다 새 예산을 적용합니다. 저장된 Run을 만들지는 않습니다.
`preview()`는 RunEngine과 메모리 저장소를 사용합니다. 둘 다 원격 서버에 코드나 근거를 업로드하지 않습니다.
ADR-079/080과 [Method 개발 가이드](guides/methods.md)를 참고하세요.

`@method`는 typed Python signature를 기존 manifest/Method adapter로 변환합니다. 입력 map은 canonical bindings로 정규화합니다. `ctx.aggregate/entities`가 관리되는 DatasetSpec을 만들고, `ctx.compute`는 로컬 직접 디버깅 또는 서버 자식 프로세스 계산을 사용합니다. 선택적 의존성은 조회 전에 검사합니다. 별도 provider planner·notebook 제품·동적 코드 설치기를 추가하지 않습니다. ADR-081과 [개발 검증](guides/development.md#tests)를 참고하세요.

분석 작성자는 계산 함수에서 외부 라이브러리의 원래 Python API를 사용합니다.
`ctx.compute`는 estimator 추상화가 아닌 실행 경계입니다. 분석별 가정과 적합
조건은 명시적으로 작성하고, 공통 실행부는 semantic 권한·추출 제한·근거를
관리합니다. 기존 builtin의 helper 재사용이 새 Method의 확장 API를 뜻하지 않습니다.

## Method와 Recipe의 경계

Method는 하나의 분석 기능이며, 여러 쿼리와 결과 조합을 내부에서 수행할 수 있습니다.
기본 Method에는 aggregate, trend, drilldown, peer comparison, CEM, 개체 변화·분포,
OLS, DoWhy 조정 대비, EconML DML, panel 대비가 있습니다.
구현은 `methods/` 바로 아래에 있습니다. `query.*`·`causal.*` ID는 호환성을 위해 유지하며,
폴더나 이름만으로 인과 주장을 정당화하지 않습니다.

`methods/__init__.py`는 작성용 타입을 공개하고 기본 Method를 명시적으로 등록합니다.
팀의 Python·Skill 정의는 `decision-layer.yaml`이 있는 프로젝트의
`<이름>/methods/` 아래에 둡니다. `method.py`의 `METHOD` 객체와 `SKILL.md`를 CLI,
로컬 `MethodSession.load_project`, API가 같은 로더로 읽습니다. `list`에서 원본
경로를 확인하며 운영에서는 `DL_PROJECT_DIR`로 프로젝트를 선택합니다. 기존
모듈·Skill 디렉터리 등록도 호환됩니다. ADR-106과
[프로젝트 가이드](guides/method-projects.md)를 참고하세요.
구현 모듈은 import만으로 자신을 등록하지 않습니다. Registry는 파라미터·입력 연결을 검사하고,
해석 범위·실행 근거를 기록하며, 선언하지 않은 artifact 타입·선택·기능을 거절합니다.
출력 수치와 payload의 정확성은 독립적인 Method 테스트가 필요합니다.
`Artifact.data`는 완전한 payload 스키마가 아닙니다.

Recipe는 조직의 절차를 기존 Method와 시맨틱 참조로 표현합니다.
지표 SQL이나 원본의 접근·검증 규칙을 재정의하지 않습니다.
입력 출처 규칙은 실행 입력과 앞 단계 선택을 연결합니다. Pipeline 모드는 고정 단계를 실행하고,
investigation 모드는 허용된 Method 선택을 제한된 범위에서 추가합니다.
ADR-003/019/060/062/067/069/070을 참고하세요.

## 시맨틱 provider

초기 제품 연결은 Cube REST만 지원합니다(ADR-096). dbt·BigQuery·DW·DM 직접 연결은 초기 범위에서 제외합니다. 기존 dbt 코드는 과거 계약 회귀용으로 보존하며 제품 연결 목록에는 제공하지 않습니다.
별도의 MetricFlow gateway는 제공하지 않습니다. Adapter는 원본 metadata를
SemanticCatalog로 변환하고 DatasetSpec을 실행합니다. 선언된 관계는 탐색 정보이며,
join·grain 지원을 보증하지 않습니다. 실제 실행에서 다시 검증합니다.

지표·차원·entity·join·집계·grain·권한은 provider가 관리합니다.
건수와 비율 구성요소는 선언되었거나 adapter가 확인한 것만 사용합니다.
Method는 주변 이름으로 의미를 추측하거나 metadata를 만들어서는 안 됩니다.
Metadata가 부족하면 통계 분석이 제한될 수 있습니다.
ADR-057/058/065/073/074와 연결 가이드를 참고하세요.

## 범위·검증·근거

실행 정책은 기간·시간 제한·쿼리 수·반환 행 수를 관리합니다.
기간이 정해지지 않으면 입력을 요구하며, 전체 기간 실행은 명시적인 정책 허용이 필요합니다.
현재 기간은 Run 범위 안에 있어야 하고 비교 기간은 정책에 따라 그 이전일 수 있습니다.
조회된 날짜 범위와 데이터 적재 완료는 다릅니다(ADR-064/072).

각 논리적 조회는 실행 전에 DatasetSpec을 기록합니다. 실패·중단도 예산에 포함합니다.
원본에서 제공하는 쿼리 ID·SQL·최신성, 경고·Method 버전·확정된 입력 출처를 확인할 수 있습니다.
쿼리 성공만으로 분석 정답을 보증하지 않습니다. 검증 실패 시 지원 기능을 제공하지 않습니다.
통계적 불확실성과 인과 해석에는 별도의 가정이 필요하며, CEM 자체가 인과효과를 식별하지는 않습니다.

MCP 실행은 질문별 목표·목적이 있는 단계·근거에 연결된 결론을 요구합니다.
임의로 생성한 분석 Python/SQL은 실행 경로가 아닙니다.
입력 규칙과 결과 기능으로 선택을 지원하며 서술에서 의도를 추측하지 않습니다.
ADR-059/069/070/071을 참고하세요.

## 접근과 저장

Provider 인증 정보는 호출자 범위에 속합니다. Run은 인증된 호출자 소유입니다.
공유된 Run은 읽기 전용이며 시맨틱 접근 권한도 필요합니다. 연결 설정은 별도로 관리합니다.
인증·설정 규칙은 공통 HTTP 의존성에 있고 각 UI에 복제하지 않습니다.

Run은 Recipe·Method 스냅샷, 실행 설정·시도·결과·근거를 저장합니다.
코드나 Recipe가 바뀌어도 과거 근거를 덮어쓰지 않습니다.
Recipe는 버전이 있는 YAML이며 Run 저장소는 메모리·SQLite·PostgreSQL을 지원합니다.
백그라운드 작업은 프로세스 내부 worker pool이며 분산 스케줄러가 아닙니다.
복구 시 중단된 작업을 표시합니다. ADR-024/029/030/070을 참고하세요.

## HTTP와 웹의 역할

`api/app.py`는 provider·저장소·작업·middleware·라우트를 조립합니다.
리소스 모듈(`sources`, `semantic`, `methods`, `recipes`, `runs`)은 공통 서비스와 엔진에 위임합니다.
Recipe 시맨틱 검사는 작성 모듈에 있으며 검증과 Run의 Recipe 등록에서 재사용합니다.

웹은 공통 실행 명세를 작성합니다. Method metadata로 입력을 만들고 artifact renderer로 결과를 표시합니다.
Recipe·Run UI는 기능별 폴더에 있습니다. 기존 타입으로 만드는 새 Method는 프런트엔드·REST·MCP에
Method 이름별 분기를 추가할 필요가 없어야 합니다.

## 부족한 정의와 확장

Run은 해결하지 못한 목표·부족한 시맨틱 정의·검토용 provider YAML 초안을 기록할 수 있습니다.
사용자는 웹에서 제안과 근거를 보고 외부에서 모델을 수정한 뒤 다시 질문합니다.
기존 검토·재시도 API는 호환성을 유지합니다. 초안으로 원본 모델을 수정하거나 실행하지 않습니다(ADR-075–078).

Method는 검토된 Python과 독립 테스트로, Recipe는 공통 명세로, provider는 기존 계약으로 확장합니다.
무거운 라이브러리는 의존성과 실행 버전 근거를 명시합니다.
노트북 호스팅·코드 업로드 실행·동적 플러그인 설치·별도 프런트엔드 런타임·범용 스케줄러는 보류합니다.

Python 호출자는 함수 인자를 이름 그대로 사용하며 정규화와 role/parameter 분류는 내부에 둡니다. 새 통계 Method는 AnalysisDesign·가정 체크박스 없이 제한된 개별 계약을 사용하고 가정 미검증·연관성 결과를 기록합니다. 기존 ID·버전의 원래 계약은 호환 모듈에 유지합니다(ADR-084).

## 쿼리 실행 Skill 단계 (ADR-098)

ADR-097의 참고용 Skill 제한을 확장한다. `query_execution: true` Markdown은
Recipe/Run 단계로 등록되며, 실행기는 외부 Claude/Codex의 쿼리 선택을 기다린다.
`run_skill_query`는 기존 ExecutionContext로 Cube 조회를 수행하고 쿼리 요청·결과·
오류·작성 클라이언트를 저장한다. `finish_skill_step`은 실제 결과 행을 참조하는
선택을 저장하고 다음 Skill 또는 Python 단계로 이어간다. Skill 본문 준수와 동료
집단 타당성을 자동 검증하지 않는다.

기본 드릴다운·peer 조사는 `analysis.drilldown`, `analysis.peer_comparison`
Skill이며, `query.drilldown`, `query.peer_comparison` Python 구현은 기존 Recipe
호환용으로 유지한다. 새 Skill은 별도 ID이므로 과거 Run 의미를 바꾸지 않는다.
`selected_group.evidence.filters`에는 제외·범위 조건도 보존되며, 후속 Python
`DataInput.filters_parameter`가 전체 조건을 입력 조회에 적용한다.

대기 중인 단계·지침 버전·해시·쿼리는 Run 저장소에 유지된다. 중단된 쿼리는
자동 재실행하지 않는다. Web은 외부 AI 실행을 기다리는 상태와 실제 쿼리 로그를
표시한다. 서버 자체 LLM, 임의 Python/SQL 실행, 새 데이터 연결은 추가하지 않는다.

## 한국어 조회 Skill과 추이 계산 분리 (ADR-099)

기본 지표 조회·추이 조사는 `analysis.metric_lookup`, `analysis.trend`가 담당한다.
계산·검사는 `stats.period_change`, `stats.series_diagnostics`에서 실행한다.
`query.aggregate`, `query.trend`는 이전 구현·버전 그대로 호환 등록하며, 기본 목록에서
제외한다. 배포 Skill은 한국어이고 기존 지침 번역은 1.0.1로 구분한다.
1.0.0을 고정한 Skill Recipe는 새 버전으로 검토·게시해야 하며 과거 Run은 보존한다.


학습 노트북은 `docs/tutorials/`, 예제 코드는 `examples/`, 자동 검증은 `tests/examples/`에 있습니다. [저장소 구조](guides/development.md)에서 전체 위치를 확인하세요.
