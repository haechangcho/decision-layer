# 저장소 구조

| 폴더 | 역할 |
| --- | --- |
| `src/decision_layer/` | 설치되는 Python 제품 코드: 입력 계약, 실행, 데이터 연결, API, MCP |
| `web/` | 관리자 화면: `app/`은 페이지, `features/`는 기능별 화면, `components/`는 공통 UI |
| `docs/guides/`, `docs/ko/guides/` | 영어와 한국어 사용 가이드 |
| `docs/tutorials/` | 직접 실행하며 배우는 노트북 |
| `examples/` | 예제 함수, 완성 프로젝트, 실행 가능한 데모 |
| `tests/` | 단위 테스트, 연결 검증, 예제 검증. 공통 도구는 `support/` |
| `scripts/` | 개발 환경 준비, 포맷 검사, 배포 확인 |

## 어디에 작성하나요?

- 팀의 Method는 팀 프로젝트의 `<name>/methods/<method>/method.py`에 작성합니다.
  [완성 프로젝트](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)를
  참고하세요. 제품 내부 코드를 수정할 필요는 없습니다.
- 학습용 노트북은 `docs/tutorials/`, 노트북이 사용하는 함수와 예제 데이터는
  `examples/`, 실행 검증은 `tests/examples/`에 둡니다.
- Method 화면은 `web/features/methods/`, Recipe 화면은 `web/features/recipes/`,
  Run 화면은 `web/features/runs/`에 둡니다.
- 실행 동작은 공통 Python 엔진에서 수정합니다. Web, REST, MCP가 같은 코드를
  사용합니다. 세부 위치는 [아키텍처](../ARCHITECTURE.md)를 참고하세요.

`decision_layer.methods`는 공개 API입니다. 기본 Method 목록은 `methods/catalog.py`,
이전 버전 등록은 `methods/compatibility.py`에서 관리합니다. 기존 구현 모듈의
import 경로는 저장된 정의와 실행 프로세스가 계속 사용할 수 있도록 유지합니다.

## 빌드 결과와 로컬 데이터

관리자 화면의 소스는 `web/`에 있습니다. `npm --prefix web run build:console`을
실행하면 Python 패키지에 포함할 파일이 `src/decision_layer/static/`에 생성됩니다.
빌드된 파일을 직접 수정하지 않습니다.

`.venv/`, `node_modules/`, `.next/`, VitePress 빌드 결과는 로컬 생성 파일입니다.
사용자 프로젝트의 DB와 게시 파일은 `.decision-layer/`에서 관리합니다.

## 이전 예제 경로

기존 `examples/methods/patterns/`에 섞여 있던 자료를 나눴습니다.
노트북은 `docs/tutorials/methods/`, Python 코드는 `examples/methods/authoring/`,
`statistics/`, `scenarios/`, `examples/recipes/`에 있습니다.
이전 예제 모듈을 `DL_METHOD_MODULES`에 지정했다면 새 경로로 바꾸세요.
과거 실행 근거에 기록된 경로는 당시 기록 그대로 유지합니다.

제품 코드도 역할별로 나눕니다. `methods/function/`은 함수 등록과 실행, `runs/`의
`access.py`, `context.py`, `steps.py`는 권한 확인과 조회 준비, 단계 실행을 맡습니다.
MCP 응답 정리는 `mcp/presentation.py`, Recipe 입력 폼은 `web/features/recipes/`에서
관리합니다. 자세한 내용은 [실행 구조](../../ARCHITECTURE.md#internal-execution-boundaries-adr-111)를 참고하세요.
