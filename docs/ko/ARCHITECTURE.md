# 아키텍처

Provider, 실행 엔진, 인터페이스를 수정할 때 참고하는 문서입니다.
첫 Method 개발은 [개발 가이드](guides/methods.md)부터 시작하세요.

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
| 쿼리 fixture | `src/decision_layer/testing.py` |
| 시맨틱 계약·Cube/dbt adapter | `src/decision_layer/semantic/` |
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
ExecutionContext.dataset(DatasetSpec)
        ↓
시맨틱 provider → 제한된 Dataset
        ↓
MethodOutput → 검증 → Result → Run 근거
```

로컬 `MethodSession.run()`은 같은 Registry와 context를 호출자의 이벤트 루프에서 실행합니다.
Breakpoint를 사용할 수 있고 실행마다 새 예산을 적용합니다. 저장된 Run을 만들지는 않습니다.
`preview()`는 RunEngine과 메모리 저장소를 사용합니다. 둘 다 원격 서버에 코드나 근거를 업로드하지 않습니다.
ADR-079/080과 [Method 개발 가이드](guides/methods.md)를 참고하세요.

## Method와 Recipe의 경계

Method는 하나의 분석 기능이며, 여러 쿼리와 결과 조합을 내부에서 수행할 수 있습니다.
현재 기본 Method는 aggregate, trend, drilldown, peer comparison, CEM입니다.
구현은 `methods/` 바로 아래에 있습니다. `query.*`·`causal.*` ID는 호환성을 위해 유지하며,
폴더나 이름만으로 인과 주장을 정당화하지 않습니다.

`methods/__init__.py`는 작성용 타입을 공개하고 기본 Method를 명시적으로 등록합니다.
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

제품 연결은 Cube REST와 공식 hosted dbt Semantic Layer GraphQL API입니다.
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
