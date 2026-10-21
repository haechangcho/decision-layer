# 코드 구조

Decision Layer를 수정할 때 실행 흐름과 코드의 위치를 확인하는 문서입니다. 개발 환경과 명령어는 [개발 환경과 테스트](guides/development.md)에 있습니다.

## 책임 구분

| 영역 | 책임 |
|---|---|
| Semantic layer | 지표, 차원, 개체, 조인, 집계와 접근 권한 |
| Method | 하나의 분석 계산 또는 AI가 따를 분석 지침 |
| Recipe | 기존 Method와 semantic 참조를 조합한 재사용 절차 |
| Run | 실행한 입력, 버전, 쿼리, 검증과 결과 |

Cube REST가 현재 제품의 데이터 연결입니다. 기존 dbt 코드는 호환 검증용으로 남아 있지만 새 연결로 제공하지 않습니다.

## 코드 위치

| 위치 | 담당 |
|---|---|
| `src/decision_layer/core/` | 공통 모델과 식별자 |
| `methods/` | Method 등록, 탐색, 입력 검사와 계산 |
| `methods/function/` | 일반 함수의 등록, 데이터 조회와 계산 단계 |
| `recipes/` | Recipe 파일, 입력 연결과 절차 검증 |
| `runs/` | 실행 상태, 단계, 제한, 접근 검사와 저장 |
| `semantic/`, `sources/` | Cube adapter, catalog와 연결 설정 |
| `api/`, `mcp/` | 공통 실행 모델을 제공하는 REST와 MCP |
| `project.py`, `project_scaffold.py`, `cli.py` | 프로젝트 읽기, 파일 생성과 CLI |
| `console.py`, `demo/` | 설치형 관리자 화면과 샘플 실행 |
| `web/features/` | Method, Recipe와 Run 화면 |
| `tests/`, `tests/support/` | 제품 검증과 공통 테스트 데이터 |
| `docs/tutorials/`, `examples/` | 학습 노트북과 가져다 쓸 예제 코드 |

표의 Python 경로는 `src/decision_layer/`를 기준으로 합니다. `methods/catalog.py`가 기본 Method를 조립하고 `methods/compatibility.py`가 이전 버전을 관리합니다.

## 공통 실행 흐름

```text
Web / REST / MCP
        ↓
RunEngine: 실행 상태, 입력과 정책 확인
        ↓
MethodRegistry: 등록된 버전과 입력 조건 확인
        ↓
ExecutionContext: 범위와 권한 검사, 조회 시도 기록
        ↓
Cube: 데이터 조회
        ↓
Method: 계산과 검증
        ↓
Result → Run 저장 → 화면과 AI에 반환
```

`runs/engine.py`는 상태와 작업을, `runs/steps.py`는 개별 단계를, `runs/context.py`는 조회와 기록을 담당합니다. `runs/policy.py`와 `runs/access.py`는 실행 제한과 읽기 권한을 관리합니다.

`MethodSession.run()`은 개발용으로 Registry와 Context를 직접 사용합니다. 계산을 현재 Python 프로세스에서 실행해 디버깅할 수 있으며 서버 Run을 만들지 않습니다. 서버의 Python 계산은 제한된 자식 프로세스에서 실행됩니다.

## Method 등록과 실행

일반 함수의 `Column`과 `DataInput` 선언은 공통 manifest와 입력 조건으로 변환됩니다. Web, REST와 MCP가 이 manifest를 읽으므로 Method마다 별도 화면이나 실행 코드를 만들지 않습니다.

`methods/function/registration.py`는 등록 정보를 만들고, `inputs.py`는 조회한 열을 함수 입력에 연결하며, `execution.py`는 데이터를 검사하고 함수를 호출합니다. 함수에는 provider나 인증 정보를 전달하지 않습니다.

팀 프로젝트의 루트에는 `decision-layer.yaml`, `methods/`, `recipes/`를 둡니다. 설정 버전 2에서는 프로젝트 이름과 Python 파일 경로를 분리합니다. 프로젝트마다 독립된 import 공간을 사용하며 서버의 계산 프로세스도 이를 복원한 뒤 함수를 읽습니다. 설정 버전 1의 기존 폴더 구조도 계속 지원합니다(ADR-120). Python 세션, CLI와 서버가 `project.py`의 같은 로더를 사용합니다. 설치 모듈을 추가하는 이전 설정도 호환 지원합니다.

Skill 실행은 외부 AI 클라이언트가 이끕니다. `runs/skills.py`가 구조화된 Cube 쿼리를 검사하고 실제 요청과 결과를 기록합니다. 실행할 때 공통 도구 지침인 `analysis-core`와 개별 분석 절차를 각각 기록하고 REST와 MCP로 AI에 함께 전달합니다(ADR-121). 파이프라인은 AI의 조회와 완료를 기다린 뒤 이어집니다. 지침을 읽는 것만으로 실행이나 검증을 통과한 것으로 취급하지 않습니다.

## 범위, 검증과 근거

- 조회는 선택한 기간, 공통 필터, 권한과 쿼리 예산을 따라야 합니다. 전체 기간 조회는 명시적 선택과 정책 허용이 필요합니다.
- 각 조회 시도는 실행 전에 기록합니다. 실패나 중단도 기록과 예산에 반영합니다.
- Entity 조회는 provider가 선언한 키와 행의 유일성을 확인합니다. 여러 조회 사이의 동일한 warehouse snapshot은 보장하지 않습니다.
- 조회 성공과 분석 타당성은 별개입니다. 검증 실패 시 지원하는 결론과 capability를 제한합니다. 연관성이나 가정에 의존한 결과를 인과효과로 바꾸지 않습니다.
- MCP의 한 질문은 목표, 단계와 근거가 연결된 하나의 Run으로 기록합니다. AI가 임의로 만든 Python이나 SQL을 실행하는 경로는 제공하지 않습니다.

## 버전과 저장

Recipe는 버전이 있는 YAML이며 Run은 별도 저장소에 실행 당시의 Method와 Recipe, 입력, 쿼리, 결과를 보존합니다. Run 저장소는 메모리, SQLite와 PostgreSQL을 지원합니다. 버전 변경이 과거 기록을 다시 쓰지는 않습니다.

`methods/source.py`는 실행한 코드의 원본과 해시를 기록합니다. 모든 외부 라이브러리와 동적 import를 보관하는 기능은 아닙니다.

선택적으로 사용하는 Method 편집기는 `methods/assets.py`에 초안과 게시 버전을 관리합니다. 설치된 Git 파일을 덮어쓰지 않으며 자동으로 Git과 동기화하지 않습니다. 고정한 버전이 없거나 설치본과 게시본의 같은 버전이 충돌하면 조용히 대체하지 않습니다.

백그라운드 작업은 프로세스 내부에서 실행하고, 복구 시 중단 상태를 기록합니다. 분산 스케줄러는 포함하지 않습니다.

## 설치와 권한 경계

PyPI 패키지는 Python 서버와 빌드된 관리자 화면을 포함합니다. `console.py`가 API와 `/ui`를 함께 제공하고, 프론트엔드 소스는 `web/`에서 관리합니다. 배포 CI가 만든 `src/decision_layer/static/`은 직접 편집하지 않습니다. VitePress 문서 사이트는 별도로 배포합니다.

`decision-layer demo`는 샘플 PostgreSQL과 Cube만 Docker로 실행하고 설치된 서버를 시작합니다. 자체 프로젝트와 컨테이너를 사용하며 회사의 연결 설정을 물려받지 않습니다. 새 데모는 패키지에 포함된 적재기와 Cube 모델로 Complete Journey의 8개 테이블 전체를 적재합니다. 설치된 Python이 로컬 전용 임시 포트로 PostgreSQL에 접속하고, Cube는 읽기 전용 계정을 사용합니다. 원본 파일은 공식 배포처에서 받아 프로젝트에 캐시합니다. 원본 데이터는 PostgreSQL 볼륨, Run은 샘플 프로젝트의 SQLite에 남습니다. 이전 합성 데모는 기존 데이터와 볼륨을 유지합니다(ADR-119).

현재 지원 범위는 로컬과 격리된 데모입니다. 공유 배포는 별도 애플리케이션 인증과 실행 격리가 준비될 때까지 차단합니다. Source 관리는 관리자 키와 승인된 주소를 요구하고, Recipe와 Method 편집 및 게시 권한은 구분합니다.

Run은 실행한 호출자에게 속합니다. 공유된 Run의 읽기에도 semantic 접근 권한을 검사합니다. Python 모듈 import와 게시 코드는 신뢰한 운영자 코드이며, 자식 프로세스 검사가 비신뢰 코드를 위한 sandbox는 아닙니다.

## 변경할 때

새 계산은 Method, 기존 계산의 조합은 Recipe, 데이터 조건은 Validator에 추가합니다. 지표 정의와 조인은 Cube에서 수정합니다. 모델 보완 초안은 검토용이며 원본을 자동 수정하지 않습니다.

구현 변경 전에는 [제품 맥락](https://github.com/haechangcho/decision-layer/blob/main/docs/PRODUCT_CONTEXT.md)을 확인하고, 설계가 바뀌면 [결정 기록](https://github.com/haechangcho/decision-layer/blob/main/docs/DECISIONS.md)을 갱신합니다. 과거 구현의 변경 이력도 결정 기록에서 확인할 수 있습니다.
