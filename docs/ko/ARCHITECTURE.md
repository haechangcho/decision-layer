# 아키텍처

Decision Layer는 semantic 참조, 검토된 Method, 재사용 가능한 Recipe를 실행하고 근거를
Run에 기록합니다. 웹·REST·Python·MCP가 같은 계약과 실행 규칙을 사용합니다.
상세 정책과 변경 이유는 [결정 기록](../DECISIONS.md)에 보존합니다.

## 코드 위치

| 책임 | 위치 |
| --- | --- |
| 공통 타입·ID | `src/decision_layer/core/` |
| Method 계약·등록·구현 | `src/decision_layer/methods/` |
| 로컬 개발 SDK | `src/decision_layer/dev.py` |
| 쿼리 fixture 도우미 | `src/decision_layer/testing.py` |
| semantic 계약·Cube/dbt adapter | `src/decision_layer/semantic/` |
| 연결 설정·인증 정보 저장 | `src/decision_layer/sources/` |
| Recipe 작성·검증·등록 | `src/decision_layer/recipes/` |
| 실행·작업·근거·저장 | `src/decision_layer/runs/` |
| REST 조립과 리소스별 라우트 | `src/decision_layer/api/` |
| MCP adapter | `src/decision_layer/mcp/` |
| 웹 페이지 | `web/app/` |
| Recipe·Run UI | `web/features/recipes/`, `web/features/runs/` |
| 공통 입력·결과 UI | `web/components/` |
| 테스트 공용 provider·factory | `tests/support/` |
| 실행 가능한 기여 예제 | `examples/methods/` |

## 실행 흐름

```text
웹 / REST / Python / MCP
  → 실행 명세 또는 Recipe
  → RunEngine: 범위·권한·선택·정책·근거
  → MethodRegistry: 입력·기본값·출력 계약
  → Method.run(ctx, bindings, params)
  → ctx.dataset(DatasetSpec)
  → semantic provider → Dataset
  → MethodOutput → 검증 → Result → Run 기록
```

로컬 `MethodSession.run()`은 같은 Registry와 context를 현재 이벤트 루프에서 실행해
breakpoint를 지원합니다. 저장된 Run을 만들지 않습니다. `preview()`는 기존 RunEngine과
로컬 메모리 저장소를 사용합니다. 원격 서버로 코드를 등록하거나 결과를 업로드하지 않습니다.
[Method 개발 가이드](guides/methods.md)를 참고하세요.

## Method와 Recipe

Method는 하나의 분석 기능입니다. 여러 쿼리와 조합을 내부에서 수행할 수 있습니다.
구현은 `methods/`에 모여 있고 `__init__.py`의 명시적인 함수가 built-in을 등록합니다.
`query.*`, `causal.*` ID는 기존 Recipe 호환성을 위해 유지합니다. 폴더나 이름만으로
인과 주장을 정당화하지 않습니다.

Registry는 입력·선택·capability·artifact 타입을 검사합니다. 출력 payload와 수치의
정확성은 독립적인 Method 테스트로 확인합니다. Recipe는 조직의 절차를 기존 Method와
semantic 참조로 표현하며 지표 수식이나 권한을 재정의하지 않습니다.

## 데이터·검증·근거

연결은 Cube REST와 공식 dbt Semantic Layer GraphQL API입니다. provider가 정의·join·grain·
집계·권한을 관리합니다. count와 비율 구성요소는 선언 또는 확인된 것만 사용합니다.
관계 metadata만으로 실제 조합이 가능한지 보증하지 않습니다.

실행 정책이 기간·시간·쿼리 수·반환 행 수를 제한합니다. 각 논리적 조회의 명세를 실행 전에
기록하고 실패·중단도 예산에 포함합니다. 실제 질의·SQL·버전·입력·경고·검증을 조사할 수 있습니다.
달력 기간 완료와 데이터 적재 완료는 다릅니다. 실패한 검증은 지원 capability를 제공하지 않습니다.
CEM의 매칭이나 관측 차이만으로 인과효과가 확인되는 것은 아닙니다.

MCP는 질문·목표·목적이 있는 단계·근거에 연결된 결론을 요구합니다.
임의로 생성한 분석 Python/SQL을 실행하는 경로를 제공하지 않습니다.

## 인터페이스와 저장

`api/app.py`는 연결·저장·작업·middleware를 조립하고, 리소스별 라우트가 공통 엔진을 호출합니다.
웹은 canonical spec을 작성하고 명세 기반 입력과 지원 artifact renderer를 사용합니다.
Method별 프런트엔드 분기를 추가하지 않습니다.

Run은 호출자 소유이며 공유해도 semantic 접근 검사가 필요합니다. Recipe는 버전이 있는 YAML,
Run은 메모리·SQLite·PostgreSQL 저장소를 사용합니다. 과거 근거는 새 코드로 덮어쓰지 않습니다.
백그라운드 작업은 프로세스 내부 worker이며 분산 스케줄러를 의미하지 않습니다.

모델의 부족한 정의와 검토용 YAML을 근거로 기록할 수 있습니다. 웹에서 제안을 보고
semantic 모델을 외부에서 수정한 뒤 다시 질문합니다. 자동으로 모델을 적용하지 않습니다.
노트북 호스팅, 코드 업로드 실행, 동적 패키지 설치, 범용 DAG 엔진은 범위 밖입니다.

자세한 정책은 영어 [현재 아키텍처](../ARCHITECTURE.md)와 ADR을 참고하세요.
