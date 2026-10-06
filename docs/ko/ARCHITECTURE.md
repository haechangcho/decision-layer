---
title: 아키텍처
description: Semantic layer, Method, Recipe, Run과 공통 실행 엔진의 책임 경계입니다.
---

# Decision Layer 아키텍처

이 문서는 [영문 아키텍처 문서](../ARCHITECTURE.md)의 한국어판입니다. 개념 인터페이스와 예시는 설계 의도를 설명합니다. 실제 API 계약은 실행 중인 서버의 `/docs`와 코드에서 확인하고, 이후 변경된 결정은 [ADR 기록](../DECISIONS.md)을 따릅니다.

## 1. 설계 목표

작고 조합 가능한 핵심 엔진으로 다음 기능을 지원합니다.

- 하나 이상의 semantic provider
- 원자적 분석 기능인 Method 레지스트리
- 재사용 가능한 Recipe
- 정해진 절차 실행과 허용 범위 내 단계별 탐색
- 타입이 정해진 검증과 결과
- 실행 근거와 출처
- 웹·Python·REST·MCP의 동일한 실행 동작

각 확장 방향은 서로 독립적이어야 합니다.

```text
Semantic provider: Cube REST → dbt Semantic Layer GraphQL → ...
Method: Drilldown → CEM → DiD → Forecast → ...
Recipe: 매출 조사 → 유지율 조사 → ...
인터페이스: 웹 → Python → REST → MCP
```

새 Method를 추가할 때 인터페이스별 엔진을 따로 만들지 않고, 새 provider를 추가할 때 기존 Recipe의 분석 논리를 다시 구현하지 않습니다.

## 2. 전체 실행 흐름

```text
사용자 / AI 클라이언트
        ↓
웹 · Python · REST · MCP
        ↓
Analysis API
        ↓
Recipe 선택 · Analysis Plan
        ↓
Recipe 레지스트리 · Method 레지스트리 · Validator
        ↓
Dataset Planner
        ↓
Semantic Provider API
        ↓
데이터 웨어하우스
        ↓
필요한 데이터셋
        ↓
Method 실행 · 검증
        ↓
타입이 정해진 Result · 실행 근거
```

자연어의 의도 해석과 설명은 클라이언트가 담당합니다. MVP 서버는 LLM을 호출하지 않으며, 제안된 단계를 공통 계약으로 검증하고 실행합니다(ADR-021).

## 3. 핵심 패키지

모듈 이름보다 책임의 경계를 유지하는 것이 중요합니다.

| 패키지 | 책임 |
| --- | --- |
| `core/` | ID, 공통 모델, 결과, 오류, capability |
| `semantic/` | Provider 계약, catalog, DatasetSpec, provider별 어댑터 |
| `methods/` | Method 계약·레지스트리, 질의·통계·인과 분석 기능 |
| `recipes/` | Recipe 스키마, 저장·조회, 계획과 실행 |
| `validation/` | Validator 계약, 등록과 기본 검증 |
| `agent/` | 향후 의도 해석·라우팅·탐색·설명의 책임을 분리할 영역 |
| `evals/` | 분석 동작의 평가 정의와 실행 |
| `api/` | REST 인터페이스 |
| `mcp/` | 공통 API를 노출하는 MCP 어댑터 |
| `sdk/` | Python 사용자를 위한 인터페이스 |

이는 책임별 개념 구조입니다. 실제 모듈 위치는 [개발 환경 가이드](guides/development.md)의 코드 위치를 확인하세요.

## 4. 안정적인 식별자

처음부터 논리적으로 안정적인 식별자를 사용합니다.

```text
semantic://cube-prod/sales/revenue
method://query/drilldown@1.0.0
recipe://revenue-investigation@2.1.0
run://01J...
result://01J...
```

Provider별 외부 참조는 원래 형태를 유지할 수 있습니다.

```text
cube://production/sales/revenue
```

내부 모델에는 provider, instance, 외부 객체 ID와 가능한 경우 버전·해시를 보존합니다. 향후 외부 그래프가 내부 DB ID에 종속되지 않고 이 객체들을 참조할 수 있게 합니다.

## 5. Semantic Provider 계약

Provider는 관리되는 의미 정의와 데이터 접근을 담당합니다. 개념 인터페이스는 다음과 같습니다.

```python
class SemanticProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    def discover(self) -> SemanticCatalog: ...
    def resolve(self, refs: list[SemanticRef]) -> list[SemanticObject]: ...
    def validate_dataset(self, spec: DatasetSpec) -> ValidationResult: ...
    def compile(self, spec: DatasetSpec) -> CompiledQuery: ...
    def execute(self, query: CompiledQuery) -> Dataset: ...
```

Provider마다 지원 범위가 다르므로 기능을 명시적으로 확인합니다.

```json
{
  "aggregate_queries": true,
  "entity_grain_queries": true,
  "time_dimensions": true,
  "join_discovery": true,
  "custom_metadata": true,
  "compiled_sql": true
}
```

Method는 필요한 capability를 선언합니다. Provider가 이를 충족하지 못하면 실행 전에 중단합니다.

## 6. 공통 Semantic Catalog

Provider별 메타데이터를 공통 내부 모델로 변환합니다. 개념상 `SemanticObject`는 ID, 이름, 종류, 데이터 타입, grain, 설명, 소유자, 최신성 정보, 외부 참조와 provider 메타데이터를 가집니다.

종류는 metric, measure, dimension, entity, time dimension으로 구분합니다. 공통 모델로 변환하면서 provider 고유 정보를 버리지 않으며, 필요하면 일반 `metadata` 맵으로 보존합니다.

## 7. Method 계약

Method는 하나의 원자적 분석 기능입니다. Manifest는 계산 자체가 아닌 실행 계약을 설명합니다.

```yaml
api_version: decision-layer/v1
name: causal.cem
version: 1.0.0
kind: causal
roles:
  unit:
    semantic_type: entity
    required: true
  treatment:
    data_type: boolean
    required: true
  outcome:
    data_type: numeric
    required: true
  covariates:
    multiple: true
    required: true
parameters:
  estimand:
    type: enum
    values: [ATT]
    default: ATT
dataset:
  grain: entity
  requires_row_level: true
execution:
  mode: dataframe
diagnostics: [balance, sample_retention]
outputs: [estimate, confidence_interval, balance, sample_summary]
```

Method는 입력 스키마, 검증, 데이터 요구사항, 실행기, 진단과 결과 스키마를 정의합니다. 지표 의미를 재정의하거나 “우리 조직의 매출은 상품별로 나눈다” 같은 조직 절차를 넣지 않습니다. UI 전용 코드를 포함하지 않습니다.

## 8. Method 실행 방식

| 방식 | 적합한 분석 | 계산 위치 |
| --- | --- | --- |
| `semantic_pushdown` | 드릴다운, 순위, 비교, 가능한 기여도 분석 | Provider·웨어하우스 중심 |
| `dataframe` | OLS, CEM, 통계 검정 | 필요한 열·행만 가져와 분석 |
| `hybrid` | 집계 후 통계 계산이 필요한 분석 | 웨어하우스 집계 + 로컬 계산 |

이 구분을 통해 불필요한 대량 추출을 줄이고 확장성을 확보합니다.

## 9. DatasetSpec과 Dataset Planner

같은 지표라도 Method에 따라 필요한 데이터 모양이 다릅니다.

드릴다운은 지표와 차원을 집계 단위로 요청합니다.

```yaml
grain: aggregate
metric: sales.revenue
dimensions: [sales.product]
```

CEM은 고객 단위 처치·공변량·전후 결과가 필요합니다.

```yaml
grain:
  entity: customer.id
fields:
  - customer.promotion_received
  - customer.age
  - customer.tenure
  - sales.revenue_30d_before
  - sales.revenue_30d_after
```

DiD는 개체와 시간으로 구성된 패널이 필요합니다.

```yaml
grain: [store.id, week]
fields: [store.ai_enabled, sales.weekly_revenue]
```

Dataset Planner는 Method의 데이터 요구사항과 semantic 입력을 읽고, provider capability를 확인하며, DatasetSpec을 만들어 provider에 컴파일·실행을 요청합니다. Method마다 소스에 직접 접속하는 경로를 만들지 않습니다.

## 10. Recipe 계약

Recipe는 재사용 가능한 분석 절차입니다. 아래는 개념 예시입니다.

```yaml
kind: AnalysisRecipe
metadata:
  name: revenue_investigation
  version: 1.0.0
  description: 매출 변화 조사
routing:
  use_for: [revenue_drop, revenue_growth, metric_change]
  do_not_use_for: [causal_effect]
semantic_scope:
  primary_metric: cube://production/sales/revenue
  related_metrics:
    - cube://production/sales/quantity
    - cube://production/sales/avg_unit_price
    - cube://production/sales/discount_rate
  preferred_dimensions:
    - cube://production/sales/product
    - cube://production/sales/region
    - cube://production/customer/segment
execution:
  mode: investigation
  allowed_methods:
    - query.compare
    - query.contribution
    - query.drilldown
    - query.related_metrics
  limits:
    max_steps: 12
    max_queries: 20
validators: [complete_period, freshness]
instructions: |
  인과 관계를 주장하지 않습니다.
  도매가 변화 대부분을 설명하면 따로 보고합니다.
output:
  sections: [headline, largest_contributors, supporting_metrics, caveats]
```

Recipe의 의미는 타입이 정해진 필드에 담습니다. 자유로운 `instructions`는 주의사항, 도메인의 함정, 보고 선호를 보완할 수 있습니다. 지표 정의, 접근 권한, Validator를 덮어쓰거나 임의 코드를 실행할 수는 없습니다.

## 11. Recipe 실행 방식

`pipeline`은 고정된 분석 절차입니다.

```text
CEM → 균형 진단 → 가중 OLS → 결과
```

`investigation`은 결과를 보면서 다음 허용 단계를 고르는 탐색입니다.

```text
다음 허용 단계 제안 → Method 실행 → Result 확인 → 검증 → 종료 또는 다음 단계
```

실행기는 허용 Method, 최대 단계·쿼리 수, provider 접근 권한, Recipe의 semantic 범위, 검증 실패를 집행합니다. LLM은 단계를 제안하고 실행기는 승인·실행합니다.

## 12. Analysis Plan

Plan은 한 요청의 구체적인 실행 의도입니다. 질문, 선택한 Recipe·버전, 해석된 semantic 참조, Method·파라미터와 단계를 기록합니다.

```json
{
  "recipe": "recipe://revenue-investigation@2.1.0",
  "question": "지난달 매출은 왜 줄었나?",
  "resolved_entities": {"primary_metric": "cube://production/sales/revenue"},
  "steps": [
    {"method": "method://query/compare@1.0.0", "params": {"comparison": "previous_complete_period"}},
    {"method": "method://query/contribution@1.0.0", "foreach": ["product", "region", "customer_segment"]}
  ]
}
```

탐색 방식에서는 결과가 나올 때 후속 단계를 추가할 수 있습니다.

## 13. 검증 구조

Validator는 조합할 수 있어야 합니다. Provider, Method, Recipe와 향후 namespace·정책 범위에서 검증을 제공할 수 있습니다.

```python
class Validator(Protocol):
    def validate(self, context) -> ValidationResult: ...
```

```json
{
  "status": "pass|warning|fail",
  "code": "DATA_STALE",
  "message": "...",
  "details": {}
}
```

| 검증 영역 | 예시 |
| --- | --- |
| 데이터 | 최신성, 빈 결과, 완전성, 기대 범위 |
| 쿼리 | 필수 필터, 완료된 비교 기간, 시간대 |
| 통계 | 최소 표본, 분산, 필요한 경우 다중공선성 |
| 인과 | 공통 지지 영역, 공변량 균형, 처치 시점, 패널 완전성 |
| 해석 | 연관성 결과에서 인과 관계를 주장하지 않도록 제한 |

## 14. Result 프로토콜

결과는 특정 화면에 종속되지 않습니다.

```json
{
  "kind": "analysis_result",
  "status": "success",
  "primary": {"type": "estimate", "value": 12430, "unit": "KRW"},
  "artifacts": [
    {"type": "breakdown_table", "data": []},
    {"type": "balance", "data": []}
  ],
  "warnings": [],
  "validation": [],
  "provenance": {}
}
```

초기 artifact는 추정값, 신뢰구간, 표, 분해표, 기여도표, 계수표, 균형 진단, 표본 요약, 시계열, 경고를 표현합니다. 웹과 MCP는 같은 결과 프로토콜을 사용합니다.

## 15. 실행 근거

Run에는 답변을 재현하거나 검토하는 데 필요한 정보를 남깁니다.

- 원래 질문 또는 호출
- 해석된 semantic 참조, provider와 instance
- 제공되는 경우 semantic 모델·버전·해시
- Recipe·Method와 각 버전
- Analysis Plan, DatasetSpec, 실행한 쿼리·명세
- 데이터 최신성, 검증과 결과
- 실행 환경·라이브러리 버전, 시각, 분석 결과

사용자가 “어떻게 계산했는가?”를 확인할 수 있어야 합니다.

## 16. 자연어 처리의 책임

| 역할 | 책임 |
| --- | --- |
| Resolver | 사용자 표현을 기존 semantic 객체에 연결 |
| Router | 직접 Method 실행과 Recipe 실행 중 선택 |
| Planner | 타입이 정해진 Analysis Plan 구성 |
| Investigator | 탐색에서 허용 목록의 다음 동작 선택 |
| Narrator | Result에 근거해 설명 |

존재하지 않는 필드를 만들지 않습니다. 설명은 기술적·연관적·인과적·진단적 해석의 범위를 따라야 합니다. 이 역할 분리는 개념 설계이며, MVP에서 LLM 역할은 외부 클라이언트가 담당합니다(ADR-021).

## 17. REST 인터페이스

API는 Sources, semantic catalog, Methods, Recipes, Plans, Runs, Results, Evals 같은 제품 객체를 노출합니다. 웹의 특정 화면에 종속된 경로를 만들지 않습니다.

```text
GET  /sources
POST /sources
GET  /semantic/catalog
GET  /methods
GET  /methods/{name}
GET  /recipes
POST /recipes
GET  /recipes/{id}
POST /plans
POST /runs
GET  /runs/{id}
GET  /results/{id}
POST /evals/run
```

이는 개념상 API 목록이며 현재 계약은 서버의 `/docs`에서 확인합니다.

## 18. MCP 인터페이스

MCP는 공통 API의 얇은 인터페이스입니다. 소스·catalog 조회, Method·Recipe 설명, 계획·검증·실행, Run·Result 조회를 제공하는 구조입니다. Method마다 별도 MCP 도구를 만들지 않습니다.

```text
list_sources · get_semantic_catalog
list_methods · describe_method
list_recipes · describe_recipe
plan_analysis · validate_analysis · run_analysis
get_run · get_result
```

실제 연결과 사용 가능한 동작은 [MCP 가이드](guides/mcp.md)를 확인하세요.

## 19. 웹 아키텍처

웹은 스키마를 기반으로 구성합니다. 루트 `compose.yaml`은 기존 소스에 연결하는 API·웹을 별도 컨테이너로 실행합니다. 웹은 `/api/*`를 API에 전달하고, SQLite와 Recipe YAML은 별도 named volume에 보존합니다. 기본 공개 포트는 localhost에 바인딩하며 샘플 데이터 환경은 `examples/`에 둡니다.

현재 Recipe 쓰기는 provider가 인정한 사용자 또는 명시적으로 활성화한 로컬 서비스 계정으로 인증하지만 작성자 역할은 검사하지 않습니다(ADR-038). Authentik 기반 애플리케이션 권한이 구현되기 전까지 API를 비공개로 유지합니다. 소스 데이터 접근 권한만으로 Recipe 편집 권한이 보장되지는 않습니다.

실행한 각 단계에는 실제 Method 파라미터와 출처(Method 기본값, Recipe, 실행 요청)를 남깁니다(ADR-039).

핵심 화면은 Sources, Recipes, Methods, Runs와 Evals입니다. Method 화면의 입력기는 semantic 객체·지표·차원·개체 선택, 선택지, 숫자, 참·거짓, 일자·시간, 구간 같은 공통 요소로 만듭니다. 분석마다 `CEMPage.tsx`, `DIDPage.tsx`, `OLSPage.tsx`를 따로 만들지 않습니다.

Recipe 편집기는 semantic 참조, 허용 Method, 관련 지표, 선호 차원, Validator, 실행 방식, 제한과 보완 지침을 구성합니다. MVP에서 범용 workflow DAG 편집기를 만들지 않습니다.

Method가 임의 React 컴포넌트를 공급하는 프런트엔드 플러그인은 MVP 범위에 없습니다. 보안·버전·빌드·디자인 시스템·샌드박스 문제가 있으므로 공통 UI 요소를 먼저 사용합니다.

## 20. Method 확장

향후 Python entry point로 Method 플러그인을 등록할 수 있습니다.

```toml
[project.entry-points."decision_layer.methods"]
synthetic_control = "decision_layer_synth:method"
```

지원하는 스키마의 Method는 API·MCP·공통 웹 UI·Recipe 편집기에서 함께 사용할 수 있어야 합니다. 이는 미래 확장 후보이며 현재 기여 방식은 [Method 가이드](guides/methods.md)를 따릅니다.

## 21. Git으로 관리할 수 있는 설정

Recipe, Validator, Eval과 참고 맥락은 장기적으로 파일로 표현하고 버전을 관리할 수 있어야 합니다.

```text
analytics/
  recipes/
    revenue-investigation.yaml
    retention-investigation.yaml
  references/
    growth.md
  validators/
  evals/
```

웹에서 편집·저장할 수 있어도 가져오기·내보내기와 버전 관리가 가능해야 합니다. 조직의 중요한 분석 지식이 불투명한 애플리케이션 DB 안에만 남지 않게 합니다.

## 22. 향후 Decision Graph와의 호환성

MVP에서 Decision Graph는 구현하지 않습니다. 안정적인 객체 ID, 명시적 semantic 참조, Run·Result ID와 외부에서 조회 가능한 메타데이터로 확장 가능성을 보존합니다.

```text
지표 → 추천 Recipe
가설 → 평가한 분석 / Run
Run → 지지하거나 반박하는 가설
결정 → 근거 Result
```

향후 그래프는 Decision Layer를 참조하는 외부 계층이며, 기본 분석 실행의 필수 조건이 되어서는 안 됩니다.
