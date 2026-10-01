# Decision Layer 제품 UX·시스템 구현 계획

작성일: 2026-10-01  
기준: `AGENTS.md`, `docs/PRODUCT_CONTEXT.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/REFERENCES.md`, `docs/MVP_PLAN.md`

## 목표

전문가가 semantic layer를 연결하고 조직의 분석 절차를 Recipe로 발행하면, 일반 사용자는 Method 설정을 몰라도 Recipe를 실행한다. MCP의 임시 분석은 동일한 Method·검증·실행 계약을 거쳐 Run에 기록되고, 전문가가 이를 검토해 Recipe 초안으로 발전시킨다.

핵심 개선 순서는 공통 Recipe 계약과 저장 경계 확립, 실행자와 작성자 UX 분리, MCP Run에서 Recipe로 이어지는 검토 경로, 개발자 기여 경험이다. KPI 그래프, BI, 스케줄러, 서버 LLM, 범용 workflow DAG는 범위에 넣지 않는다.

## 최신 우선순위 · Recipe 설정 단순화

2026-10-01 사용자 피드백 반영. 아래 항목은 구현 계획이며 완료 여부는 마일스톤 체크리스트를 따른다. 기존 Sources S1 완료 기록은 유지한다.

| 순서 | 개선할 사용자 문제 | 다음 작업 | 완료 시나리오 |
|---|---|---|---|
| 1 · U2/U3 | Recipe를 만들기 전에 실행 방식과 숫자 설정부터 이해해야 함 | 작성 시작을 사용 목적 → 분석 대상 → 분석 절차로 구성. 실행 방식 선택을 초기 화면에서 제거하고 세부 파라미터는 고급 설정으로 이동 | 전문가가 모드 용어·그룹 수·표본 수를 입력하지 않고 매출 비교와 항목별 분석 절차를 작성. 일반 사용자는 Recipe와 기간만 골라 실행 |
| 2 · U1/U3 | 옵션을 숨기면 어떤 값으로 실행되는지 불명확해짐 | 공통 기본값 해석, 조직 고정값과 실행 시 선택값의 구분, 검증 및 적용값 기록 | Web·MCP·API가 같은 생략 입력에 같은 기본값을 적용. 허용 범위를 벗어난 AI 요청은 거부하고 실제 적용값·출처가 Run에 남음 |
| 3 · U3 | 만든 절차를 믿고 재사용하기 어려움 | 단계 미리보기, 의미 있는 diff, YAML 동기화, 초안/발행, 무손실 편집 | 두 단계 Recipe를 시험 실행하고 오류 수정 → 변경 비교 → 새 버전 발행. 기존 Recipe를 열어 저장해도 숨겨진 설정이 유지됨 |
| 4 · U4 | MCP 탐색이 일회성으로 끝나며 공식 절차 등록 전 검토가 어려움 | Run 그래프 → 단계 선택 → Recipe 그래프 초안 → 사용자 검토·Approve → 등록 | 사용자가 노드별 결과·근거와 변경 내용을 확인하고 승인해야 새 Recipe 또는 기존 Recipe의 새 버전으로 등록됨 |
| 5 · U5 | 외부 기여와 설치 후 운영이 어려움 | Method 기여 템플릿·계약 테스트·예제, Docker 설치·영속화·백업 | 신규 기여 Method를 UI 전용 분기 없이 사용하고, 새 설치에서 연결·실행·재시작 후 기록 확인 |

사용자 요청으로 authentik/OIDC·토큰 자동 갱신·기업 공용 서비스 계정(Sources S2/S3)은 현재 개발 범위에서 제외한다. 기존 Cube 토큰 전달·관리자 권한·Run 소유/공유 검증은 유지한다. Git PR·다중 worker·추가 semantic provider는 핵심 여정 이후로 둔다.

### 기본 화면과 고급 설정의 경계

- 기본 작성 정보는 사용 목적, 연결된 분석 대상, 등록된 Method로 구성한 분석 절차다. 목적 문장은 라우팅·설명용이며 Web에서 LLM을 호출하거나 절차를 자동 생성하지 않는다.
- 지표는 고정하거나 실행 시 선택하게 설계한다. 실행 시 선택 기능은 필수 role·허용 semantic 범위 검증과 함께 구현한다. 현재 모든 Recipe가 이를 지원한다고 표시하지 않는다.
- `pipeline`/`investigation`은 canonical 계약으로 유지하되 첫 화면 선택을 없앤다. 기존 investigation은 허용된 분석과 탐색 범위를 보여 주고 MCP에서 이어갈 경로를 제공한다. '결과를 보고 다음 분석 선택'은 사용자 설명이며 새 조건 분기 노드/DAG 기능을 뜻하지 않는다.
- '기본 분류 순서'는 '먼저 살펴볼 항목 (선택)'으로 변경한다. 현재 `preferred_dimensions`의 순서가 실제 드릴다운에 영향을 주므로 단순한 비순서 태그처럼 표현하지 않는다. 고정 경로가 필요한 단계에서는 '나눠 볼 순서'를 별도로 보여 준다. 비어 있을 때 실행에 필수인 차원은 미리보기/실행 시 선택하고 조용히 추측하지 않는다.
- `top_n`(표시할 그룹 수), `rank_by`(정렬 기준), `min_count`(최소 그룹 건수)는 기본 폼에서 숨긴다. 고급 설정은 명시적 override와 '기본값 사용' 복원을 제공한다. 기존 Recipe의 값은 보존한다.
- `top_n`과 `rank_by`는 웹 표 꾸미기만의 옵션이 아니다. MCP 반환 후보와 후속 분석에도 영향을 주므로 적용값과 결과 절단 여부를 기록한다. `min_count`는 후보 제외/표본 정책이며 통계적 유의성을 보증하는 값으로 설명하지 않는다.

### 기본값과 AI 선택의 책임

권장 해석 순서는 실행 요청값 → Recipe 고정값 → Method 버전별 기본값이다. 단, Recipe가 고정한 값이나 조직 정책은 실행 요청이 임의로 덮어쓸 수 없으며 충돌은 거부한다. 이 구분을 표현할 최소 계약은 U1/U3에서 설계·검증하고 스키마 변경이 필요하면 ADR을 추가한다.

- 엔진: 필수 입력·타입·범위·표본 요건·실행 한도를 검증한다. AI의 선택도 같은 validator를 통과한다.
- Recipe 작성자: 질문의 적용 범위, 중요한 분석 순서와 조직이 고정해야 할 제한을 지정한다. 모든 기본값을 매번 입력할 필요는 없다.
- MCP의 AI: 허용된 Method·semantic 참조·변경 가능한 실행 옵션을 선택한다. 반환 개수 같은 사소한 선택은 기본값으로 진행하고, 지표 의미·비교 대상 등 결과 해석을 바꾸는 모호함에만 질문한다.
- 최소 표본 기준을 AI가 결론을 얻기 위해 임의로 낮추지 않도록 정책을 둔다. 기준 미달이면 제외·경고·비교 불가를 제공한다. 현재 구현의 모든 분석 경로에 이 정책이 적용돼 있다고 가정하지 말고 검증한다.
- Run: 실제 적용 파라미터, Method 버전, 값의 출처(기본/Recipe/실행 요청), 검증·제외·경고를 남긴다. UI에서 숨겼다는 이유로 근거까지 숨기지 않는다.

## 현재 구현과 차이

- Sources, Catalog 준비 상태, Method 목록·상세, Recipe 그래프 작성, 버전 YAML 저장, Run 실행·저장은 이미 존재한다. MCP Recipe 도구도 기본 활성화다.
- Recipe 상세 실행 화면과 전문가 편집 경로는 분리됐지만, 편집기는 여전히 실행 모드·분류 순서·세부 파라미터를 먼저 노출해 사용자의 업무 절차보다 엔진 설정을 요구한다.
- `web/components/recipe-editor.tsx`가 Method 이름별로 입력 UI를 분기해 ADR-014의 스키마 기반 원칙과 다르다. 고급 설정은 JSON이고 YAML 양방향 편집은 없다.
- Recipe YAML 로딩·API 사전 검증·Web 저장이 공통 정적 validator를 사용하도록 U1을 구현했다. `POST /recipes:validate?live=true`는 호출자 권한으로 semantic refs도 확인한다.
- `RecipeStore`는 요청 시 파일을 다시 읽는다. 저장 때 OS 파일 잠금 아래 최신 파일을 읽고 base version을 비교해 프로세스 간 stale write를 거부한다. 앱 경로는 기존 버전을 덮지 않는다.
- MCP는 Recipe 우선 실행과 단일 Method Run을 제공한다. Recipe 없이 여러 단계를 잇는 MCP 흐름, 전문가 검토 목록, Run에서 초안을 만드는 API는 없다.
- SQLite·PostgreSQL Run 저장소가 있다. 보존·페이지 조회·대용량 결과·다중 작업자 안전성은 별도 운영 요건으로 남아 있다.
- ADR-025(Recipe 파일), ADR-029(호출자 소유 Run), ADR-030(프로세스 내부 작업), ADR-033(암호화 Source 설정), ADR-035(Recipe 그래프)를 기준으로 확장한다. MVP_PLAN의 오래된 서버 LLM, Recipe DB 저장, Method 목록은 이 ADR들과 조정한다.
- Sources 흐름을 명시적인 API URL·인증 선택·연결 확인으로 수정했다(ADR-037). 자동 주소 탐색을 제거하고 검사/실행 인증 선택을 통일했다. 기업 OIDC와 서비스 계정의 권한·저장 경계 및 근거는 [연결 설계 검토](SOURCE_CONNECTION_DESIGN.ko.md)를 따른다. 기업 인증은 미구현이다.

## 제품 여정과 화면 책임

| 화면 | 사용자 목표 | 주요 행동과 다음 단계 |
|---|---|---|
| `/`·Recipe 라이브러리 | 적합한 절차를 골라 분석 | 업무 목적·지표 검색 → 조건 확인 → 최소 입력 → 실행 → Run 근거 확인 |
| Sources | Cube 연결·상태 확인 | 연결 테스트 → Catalog 확인. 환경변수 고정·권한·주소·인증 오류를 구분 |
| Catalog | 의미와 분석 준비 상태 파악 | 지표 정의·시간·분자/분모·entity key·제한 확인 → Recipe 작성 시작 또는 기존 Recipe 확인 |
| Methods | 전문가·기여자의 고정 기능 탐색 | 입력·출력·필요 capability·해석 제한·예제 확인 → Recipe에 추가 또는 개발 문서로 이동 |
| Recipe 편집 | 조직 절차 작성·검증·발행 | 사용 목적·분석 대상·절차 구성 → 기본값으로 미리보기 → 필요한 고급 설정만 변경 → diff → 발행 |
| Runs | 결과·실행 근거 검토 | 상태·판정·단계 결과·쿼리·semantic refs·버전 확인 → 재실행·공유·Recipe 초안 제안 |
| MCP 탐색 기록 | 선택적으로 제출된 탐색 검토 | 호출자 소유 원칙 유지 → 제출·공유 Run만 검토 → 단계를 초안화 → 다른 기간으로 재검증 |

### 편집기 원칙

- Recipe 그래프는 순서와 참조를 보여준다. pipeline은 자동 실행 순서, investigation은 허용 범위와 정책을 표시한다. 이를 임의 DAG로 일반화하지 않는다.
- Method role과 설정 UI는 manifest로 생성하되 '스키마에 있음'을 '기본 화면에 노출'과 동일시하지 않는다. 기본 폼은 꼭 필요한 선택만 제공하고 세부 파라미터는 고급으로 옮긴다. 현재 고급 JSON은 U3에서 canonical YAML 편집으로 교체한다. 출력 스키마가 확정되면 이전 단계 결과 선택을 타입에 맞게 안내한다.
- 모드 전환은 단계·설정을 조용히 버리지 않는다. 안전한 변환이 불가능하면 변환 미리보기와 복제본 생성만 제공한다.
- 저장되지 않은 변경은 페이지 이탈 경고와 복구 가능한 로컬 초안을 제공한다. 검증 오류는 입력 항목에 연결한다.
- 빈 상태에는 다음 행동, 오류에는 원인과 해결책, 권한 부족에는 필요한 권한, 비동기 실행에는 단계별 상태를 표시한다. 모든 흐름은 키보드와 좁은 화면에서 완료할 수 있어야 한다.

## 도메인·저장 경계

- Semantic provider는 지표 의미·차원·조인·grain·데이터 권한을 가진다. Decision Layer는 semantic ref만 사용하고 의미를 복제하지 않는다.
- Method는 고정된 원자 분석이며 typed 입력·출력·validation·interpretation을 제공한다. Recipe는 등록 Method의 순서·허용 범위·조직 지식이다.
- 모든 인터페이스(Web/Python/REST/MCP)는 공통 canonical spec, 검증, 실행 엔진을 이용한다. LLM은 등록된 기능 선택과 설명만 보조한다.
- Recipe YAML은 단일 정의 원본이다. 로컬 폴더 설치에서도 동작하고, DB에는 Run과 운영상태를 둔다. Git 연결 시 diff·commit·PR 정보는 파일 이력과 연결한다.
- 발행 Recipe 버전은 불변으로 취급한다. Run은 당시 Recipe snapshot, 실제 Method 버전, semantic refs, 쿼리, 검증, 경고를 보존한다. 데이터 snapshot이 없는 한 원천 데이터까지 재현 가능하다고 약속하지 않는다.
- SQLite는 영속 볼륨을 쓰는 단일 인스턴스 기본값이다. PostgreSQL은 공유 배포·동시 접근·운영 백업 요구에서 선택한다. PostgreSQL만으로 in-process 작업 실행이 다중 worker에 안전해지지는 않는다.

## Recipe 저장·리뷰 정책

1. MVP는 파일 저장과 명시적 발행을 지원한다. 초안은 기본 검색·실행에서 제외한다.
2. 모든 입력 경로가 같은 파서·정적 검증기를 사용한다. live semantic 사전 검증은 선택한 provider 권한으로 별도 표시한다.
3. 저장은 내용 해시와 base version을 비교한다. 오래된 편집은 409와 최신 diff를 반환한다. 발행 버전은 덮어쓰지 않는다.
4. MVP는 단일 작성 프로세스와 로컬 폴더를 지원한다. Git은 선택적 로컬 저장소 commit을 후속으로 지원하고 원격 PR 승인은 운영 요구가 확인된 뒤 둔다.
5. 이전 발행 버전은 읽기 전용으로 유지한다. 롤백은 과거 버전을 다시 발행하거나 변경을 새 버전으로 발행한다.
6. Run 승격은 전문가가 단계를 직접 선택한다. 기간·필터는 재사용 가능한 입력으로 바꿀지 검토하며, 우연한 결과를 Recipe 의존관계로 추론하지 않는다.

### MCP 기록 → 그래프 검토 → 승인

현재 구현: `mcp/server.py`는 `DL_API_URL`의 공통 REST API를 호출한다. `RunEngine`이 시작·단계·상태 변경 시 `RunStore`에 Run 전체를 저장한다. 저장소는 `DL_DATABASE_URL`로 선택하며 기본 설정은 `data/decision_layer.db`의 SQLite, PostgreSQL도 지원한다. `memory` 설정은 재시작 시 사라지며 Docker의 파일 DB는 볼륨이 필요하다. 이는 실제 배포의 DB 설정을 조사한 결과가 아니라 코드의 기본값과 지원 계약이다.

- 저장되는 내용: 실행 scope·질문(제출된 경우), 호출자, Recipe snapshot(Recipe 실행인 경우), 단계별 Method 버전·입력·결과·쿼리/provenance·검증·경고·시각·상태. SQL 등 근거는 provider가 제공한 범위만 포함한다.
- Claude/Codex의 전체 대화나 내부 추론은 저장하지 않는다. MCP 도구를 통한 분석 실행이 기록 대상이며 카탈로그 조회 같은 모든 도구 호출의 감사 로그는 아니다.
- 같은 API/DB와 적절한 소유·공유 권한이면 Web에서 같은 Run을 조회할 수 있다. 현재 `run_method`는 호출마다 별도 Run이고, Recipe investigation의 `run_step`은 같은 Run에 단계를 추가한다. MCP 출처/탐색 세션 식별 및 여러 adhoc Run 연결은 추가 구현 대상이다.

권장 UX (미구현):

1. **실행 기록 그래프:** Runs 상세에서 실행 단계를 읽기 전용 노드로 표시한다. 노드를 누르면 입력·결과·경고·근거를 확인한다. 실행 순서와 실제 참조 관계를 구분하고, 근거 없는 의존 간선은 생성하지 않는다.
2. **Recipe 초안 만들기:** 사용자가 단계를 선택해 새 Recipe 또는 기존 Recipe에 추가할 초안을 만든다. 여러 adhoc Run은 사용자가 묶을 기록을 명시적으로 선택한다. 이후 탐색 세션 식별이 있으면 해당 세션 안에서 후보를 제시한다.
3. **그래프 검토:** 기존 Recipe 편집기를 재사용한다. 선택 단계, 원본 Run 링크, 기간·필터의 고정/실행 시 입력 여부, 추가·삭제·수정 diff, 검증 오류를 보여 준다. 반복 실행을 막는 고정 날짜나 누락된 선행 참조는 승인 전에 해결한다.
4. **승인 후 등록:** 주 버튼은 '승인하고 Recipe 등록'이다. 등록 권한이 있는 사용자의 명시적인 승인 후에만 YAML을 새 버전으로 저장한다. AI는 초안을 제안할 수 있지만 승인 주체가 될 수 없다. 승인은 절차 등록에 대한 것이며 원본 분석의 인과성·통계적 타당성을 보증하는 표시는 아니다.
5. **보류·반려:** 검토 중 나가도 초안을 보존하고, 반려 사유를 남길 수 있다. 반려해도 원본 Run은 삭제하지 않는다. 등록 후에는 Recipe 열기·다른 기간으로 실행을 제공한다.

저장 책임: Run은 DB의 실행 근거, 검토 초안은 DB의 미발행 제안, 발행 Recipe는 YAML 파일이다. 검토 초안은 실행 가능한 Recipe의 두 번째 원본으로 사용하지 않는다. 제안에는 원본 Run/단계 참조·후보 spec·base version·revision·검증 결과·상태·검토자/시각·발행 버전을 기록한다. 초안 → 검토 대기 → 승인 및 등록 / 반려 상태를 두며, 수정되면 해당 revision의 검증·승인만 유효하게 한다.

승인 API는 기존 Recipe 등록 권한과 Run 읽기 권한을 재검사한다. 최신 버전 충돌·중복 클릭·파일 저장 실패 시 잘못된 승인 완료를 남기지 않도록 멱등 발행과 복구를 설계한다. MVP에서 GitHub PR 승인은 요구하지 않는다. DB 제안 저장 경계는 구현 전 ADR에 명시한다.

## Run DB·보존

- 저장: 소유자/공유 주체, 실행 출처(Web/MCP/API), 질문, 입력 scope, Recipe snapshot/hash, Method 버전, 단계 상태·결과, semantic refs, 실행 쿼리, validation, 경고, 생성·완료 시각.
- 제외: bearer token, 불필요한 원시 행 대량 저장, 편집 가능한 Recipe 정의의 DB 복제.
- MVP부터 스키마 migration, 기간·Recipe·소유자 기준 검색, 페이지네이션, 크기 제한, 보존·삭제 설정을 둔다. 초기 기본 보존은 운영자가 조정할 수 있게 하고 90일 Run / 30일 큰 결과를 제안값으로 둔다.
- SQLite 기본, PostgreSQL 팀 운영. 대형 artifact는 이후 외부 파일 저장소로 분리하고 DB에는 크기·해시·접근 제어가 붙은 참조만 저장한다.
- Run 공유·검토는 명시적인 제출/공유를 전제로 한다. 조직 전체 Run 열람은 ADR-029 변경 없이는 추가하지 않는다.

## Method 기여 경험

- MVP 기여는 리뷰된 Python Method 패키지다. `methods/<category>/<name>/`에 manifest, 구현, README, 예제, 정상·경계·거부 테스트를 둔다.
- manifest는 버전, semantic 입력 role, 타입·범위·기본값, capability 요구, interpretation, 구조화된 output schema, 기본/고급 표시 정보를 선언한다.
- 공통 contract test가 입력·직렬화·출력·검증·오류·Provenance를 검사한다. 예제 데이터로 설치 없이 빠르게 실행할 수 있는 기여 템플릿과 기여 가이드를 제공한다.
- YAML은 검증된 Method의 설정·Recipe 조합에 사용한다. 새 계산 로직의 표현 언어로 만들지 않는다. Claude Skill은 사용 안내·절차 문서이며 서버 실행 코드가 아니다.
- 임의 Python 업로드는 금지한다. 관리자가 고정 버전 패키지를 설치하고 서버 시작 시 등록한다. manifest의 capability는 권한 선언이지 sandbox가 아니다. 격리 실행·외부 플러그인 레지스트리는 후속이다.
- GTM의 명시 권한 계약, Obsidian의 제출·검토 문서, Claude Skills의 작은 설명 파일과 단계적 자료 공개를 참고하되 해당 플러그인 시스템을 그대로 복제하지 않는다.

## 구현 마일스톤

| ID | 범위 | 사용자 기준 완료 시나리오 | 선행·결정 |
|---|---|---|---|
| U0 | 제품 계획·체크리스트·여정 기준 고정 | 사용자가 화면별 목적과 다음 단계를 검토할 수 있고 범위가 ADR과 일치 | 완료. 신규 ADR 불필요 |
| U1 | Recipe 공통 파싱·정적 검증, 오류 위치, 충돌·저장 계약, API 연결 | 같은 YAML이 파일·Web에서 같은 오류를 보이고, 오래된 수정이 최신 Recipe를 덮지 않음 | 구현함; API 시나리오 확인 미완료. ADR-014 복원 및 025/035 저장 상태 정책 보완 |
| U2 | Recipe 실행/편집 분리, 라이브러리 우선 루트, manifest 기반 폼·오류 | 일반 사용자가 Method 이름 없이 Recipe를 찾아 입력·실행하고 Run 근거를 열람. 전문가가 편집 경로 진입 | 구현 진행 중; 실제 분석 시나리오 확인 미완료. 035 원칙 |
| U3 | 미리보기·검증·의미 있는 diff·발행·초안 상태 | 전문가는 두 단계 Recipe를 검증하고 변경을 비교해 발행, 이전 버전을 실행 기록과 함께 유지 | U1·U2. 파일 초안/발행 계약 ADR 보완 |
| U4 | MCP 탐색 식별·Run 그래프·제안 저장·검토·Approve | MCP 탐색 세 단계를 그래프로 검토하고 두 단계 선택 → 입력 일반화 → 승인 → 새 Recipe로 실행. 반려·권한 없음·충돌·중복 승인은 잘못된 발행을 만들지 않음 | U1·U3. ADR-025/033의 DB 저장 범위에 미발행 제안 추가 결정 필요. ADR-029 소유·공유 경계 유지 |
| U5 | Method 기여 템플릿·계약·문서·Docker 운영 | 새 Method 기여자가 API/MCP/Web에서 동일하게 사용되는 Method를 추가하고 Docker 재시작 후 Run을 확인 | U1·U2. ADR-015 유지 |
| 후속 | Git 원격 PR, 다중 writer/worker, 대용량 artifact 저장 | 승인·롤백·장애 복구가 여러 사용자의 실제 운영 부하에서 확인 | 배포 요구와 사용량으로 착수 |

각 완료 기준은 실제 사용자 시나리오로 Playwright/API 계약 흐름에서 확인한다. 이 문서의 신규 계획은 구현 완료를 뜻하지 않으며 검증 기록은 체크리스트에 별도로 남긴다.

## 진행을 막는 결정

현재 계획을 시작하는 데 막히는 결정은 없다. U4는 자신의 Run 또는 호출자가 명시적으로 공유·제출한 Run만 검토하고, 기존 Recipe 등록 권한이 있는 사용자가 승인한다. 별도 승인자 조직·중앙 전체 Run 열람은 이번 범위에 넣지 않는다.

## 참고 자료

- [Airflow DB 운영 가이드](https://airflow.apache.org/docs/apache-airflow/stable/howto/set-up-database.html): 단일 개발 설치와 운영 DB 구분 참고.
- [Superset 아키텍처](https://superset.apache.org/admin-docs/installation/architecture/): 메타데이터 DB와 분석 warehouse 책임 분리 참고.
- [GTM template permissions](https://developers.google.com/tag-platform/tag-manager/templates/permissions), [Obsidian plugin submission](https://docs.obsidian.md/community-directory/submission-requirements-for-plugins), [Claude Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview): 기여 문서·계약의 참고 사례.
