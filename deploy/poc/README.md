# PoC 배포 구성

새 heartcube와 Decision Layer의 PoC 배포 구성입니다.
2026-10-30에 두 `linux/amd64` 이미지를 로컬 빌드하고 임시 컨테이너에서 검증했습니다.
3단계에서 승인된 기존 PostgreSQL의 별도 `journey`, `journey_meta` 스키마에
Complete Journey를 적재하고 독립 SQL 검증을 마쳤습니다. 2026-11-02에 새 Cube 모델·설정과
Decision Layer 로그인(ADR-130)을 추가하고 별도 컨테이너로 배포했습니다.
기존 서비스의 Compose·컨테이너·네트워크·볼륨은 사용하지 않습니다.

## 계속 사용하는 PoC 브랜치

사용자 요청으로 두 저장소 모두 **`poc/deployment`** 브랜치에서 이 PoC를 계속 개선합니다.
일반 개발 브랜치와 분리하고, 수정할 때마다 새 기능 브랜치를 만들지 않습니다.
기존 `feat/*`, `poc-shared-login`, `main`은 보존합니다. 일반 개발로의 병합은 별도 요청으로 처리합니다.

| 대상 | 계속 작업할 브랜치 | 현재 검증된 기준 |
|---|---|---|
| Heartcube | `poc/deployment` | `heartcube:poc-a9e8a00` |
| Decision Layer | `poc/deployment` | `decision-layer:poc-2a67b18` |
| 외부 샘플 모델 | DL의 `poc/deployment`에서 관리 | `a3e46aa`: Cube 11개·View 3개 |

버전마다 브랜치를 늘리지 않습니다. 해당 브랜치에 커밋을 쌓고,
이미지를 `<component>:poc-<git-short-commit>`으로 새로 만듭니다.
기존 이미지는 보존하고, 같은 태그를 덮어쓰지 않습니다. 현재 기준은 `versions.json`에 기록했습니다.
브랜치 설정 변경 자체는 이미지 재빌드나 서버 재배포를 하지 않습니다.

저장소 루트에서 다음을 사용합니다. Heartcube 소스의 기본 위치는 이 저장소의 형제 디렉터리
`../heartcube`이며 다른 위치는 `--source /path/to/heartcube`로 지정합니다.

```bash
python3 deploy/poc/build_image.py heartcube --plan
python3 deploy/poc/build_image.py decision-layer --plan
# 수정·테스트·커밋 후, 변경한 프로그램만 빌드
python3 deploy/poc/build_image.py heartcube
python3 deploy/poc/build_image.py decision-layer
```

빌드 도구는 다른 브랜치, 미커밋 추적 파일, 이미 존재하는 로컬 이미지 태그를 거부합니다.
Git에서 추출한 커밋 소스만 빌드하며, 무관한 미추적 파일과 고객사 설정·비밀값은 포함하지 않습니다.
빌드 기록은 Git 제외 파일 `builds/*.local.json`으로 남깁니다. 빌드 성공과 실제 검증·배포는
별도이며, 도구는 `.env`를 바꾸거나 서버를 재시작하지 않습니다.

개선 순서는 **같은 PoC 브랜치에서 수정 → 테스트 → 커밋 → 새 이미지 빌드 → 이미지 검증 →
해당 서비스만 배포 → 실제 PoC 테스트**입니다. 모델·설정·Recipe는 외부 파일이므로
프로그램 변경이 없으면 이미지 재빌드는 필요하지 않습니다. 배포 시 두 이미지와 외부 자산 버전을
함께 기록하고, 고객사 자산은 비공개로 보관합니다.
실제 검증·배포가 끝나면 `versions.json`의 기준도 갱신해 같은 PoC 브랜치에 커밋합니다.
문서나 배포 기록만 바뀐 커밋마다 프로그램 이미지를 다시 만들 필요는 없습니다.

## 서비스와 포트

| 서비스 | 호스트 포트 → 컨테이너 포트 | 연결 대상 |
|---|---|---|
| 새 heartcube | `${BIND_ADDRESS}:5103 → 4000` | 설정한 PostgreSQL의 데모 스키마 |
| 새 Decision Layer | `${BIND_ADDRESS}:5104 → 8000` | 새 `heartcube:4000`. 원격 MCP는 `/mcp` |

| 로컬 이미지 | 검증 결과 |
|---|---|
| `heartcube:poc-a9e8a00` | 커밋 소스 재빌드. 네이티브 모듈·Python 인증·운영 모드·임시 PostgreSQL 집계 통과 |
| `decision-layer:poc-2a67b18` | 커밋 소스 재빌드. UI·REST·stdio MCP·OLS·재시작·shared 인증/개인 토큰 통과 |

이미지는 로컬 Docker에 있으며 레지스트리에 게시하지 않았습니다.
이미지 ID 등 로컬 빌드 기록은 Git 제외 파일 `images.local.json`에 남깁니다.
이전 날짜 태그는 당시 작업 트리 빌드입니다. 새 커밋 태그는 Git에서 추출한 소스만으로 빌드하고
OCI revision과 `images.local.json`에 원본 커밋을 기록합니다. 정식 릴리스는 아닙니다.

기존 서비스의 `5101`, `5102`, `15432` 포트는 사용하지 않습니다.
새 Cube의 SQL 포트, PostgreSQL, authentik 서비스는 추가하지 않습니다.
Compose 프로젝트 이름은 `decision-layer-poc`이며 네트워크·볼륨도 이 이름으로 분리됩니다.
다른 설치는 고유한 `-p <project-name>`을 사용합니다.

기본 바인딩은 localhost(`BIND_ADDRESS=127.0.0.1`)입니다. 포트와 HTTPS 프록시/로드밸런서가
준비되면 `BIND_ADDRESS=0.0.0.0`으로 바꿉니다. 기존 5101/5102도 같은 방식으로 열려 있습니다.

## 폴더와 데이터

```text
compose.yaml                 두 이미지의 연결·포트·저장 설정
.env.example                 고객사별 설정 항목 (비밀값 없음)
cube/                        Cube 설정과 semantic model
project/decision-layer.yaml  Decision Layer 프로젝트 설정
project/methods/             검토한 고객사 Python Method·Skill
project/recipes/             Recipe와 게시·변경 이력 (쓰기 가능)
journey/                     전용 DB·계정 준비 및 데이터 적재 도구
```

프로젝트 설정·Method·Cube 인증 설정은 읽기 전용으로 연결합니다.
Recipe와 Cube 모델 디렉터리는 쓰기 가능하며, 컨테이너를 교체해도 파일이 유지됩니다.
Heartcube 모델 화면은 목록 조회 때도 모델 아래 Draft/Git 상태를 초기화하므로
`cube/model/`은 쓰기 권한이 필요합니다. 모델 변경은 Heartcube의 관리자 권한으로 제한합니다.
Decision Layer 이미지는 UID/GID `10001:10001`로 실행하므로 서버 배포 시
Recipe 디렉터리에 해당 사용자의 쓰기 권한을 준비해야 합니다.
현재 프로젝트는 패키지의 기본 Methods를 사용합니다. 고객사 정의는 이후 추가합니다.

실행 기록은 우선 `decision-layer-data` 볼륨의 SQLite에 저장하는 단일 인스턴스 구성입니다.
`DL_DATABASE_URL`로 기존 PostgreSQL의 **전용 앱 DB**를 선택할 수도 있습니다.
이 경우 Cube의 읽기 계정과 별도의 쓰기 계정을 사용합니다.
PostgreSQL을 선택해도 다중 API 프로세스 실행이 지원되는 것은 아닙니다.
백업 대상은 실행 기록 저장소, `project/recipes/`, Draft/Git 이력을 포함한 `cube/model/`이며,
`docker compose down -v`는 실행 기록 볼륨을 삭제하므로 일반 종료에 사용하지 않습니다.

## 설정할 항목

| 항목 | 준비할 값 |
|---|---|
| 이미지 | 검증한 두 이미지의 고정 버전 태그 또는 digest |
| 데이터 | 데모 DB 주소·이름·읽기 계정. 고객사는 기존 DM/DW 연결 값 |
| Cube 인증 | 새 인스턴스 전용 서명키, 새 authentik 앱의 issuer·client·callback |
| Decision Layer 로그인 | 별도 authentik 앱의 issuer·client, `DL_PUBLIC_URL`, 세션 키, Cube 토큰 키 |
| 앱 주소 | 검증된 HTTPS 주소와 허용 Host/Origin |
| 실행 기록 | 기본 SQLite 볼륨 또는 별도 PostgreSQL 앱 DB URL |

DB 관리자/적재 계정과 기존 서비스의 비밀값은 이 구성에 넣지 않습니다.
고객사 모델·Method·Recipe와 실제 `.env`는 Git 제외되므로 별도 비공개 자산으로 관리합니다.

## 지금 검증할 수 있는 것

값을 준비한 뒤 이 디렉터리에서 설정 파일을 만듭니다.
이미 존재하는 `.env`는 덮어쓰지 않습니다.

```bash
test -e .env || (umask 077 && cp .env.example .env)
# .env의 필수 항목 입력 후, 컨테이너 실행 없이 문법 검증
docker compose --env-file .env -f compose.yaml config --quiet
```

빈 필수 자격증명은 검증 단계에서 거절됩니다. 전체 `config` 출력에는
입력한 비밀값이 포함되므로 공유할 때는 `--quiet`를 사용합니다.
이 검사는 설정 문법만 검증하며 이미지·DB·로그인 성공을 증명하지 않습니다.

## 이미지 빌드와 검증 재현

Git 커밋에서 추출한 소스로 빌드합니다. 정확한 절차는 [RUNBOOK 3절](RUNBOOK.ko.md#3-커밋된-코드로-이미지-빌드)을 따릅니다.
Heartcube는 기존 Dockerfile을 사용하며 개발용 Compose를 실행하지 않습니다.
아래 검증 명령은 저장소 루트에서 실행합니다.

```bash
python3 deploy/poc/smoke_decision_layer.py decision-layer:poc-2a67b18
python3 deploy/poc/smoke_heartcube.py heartcube:poc-a9e8a00
```

Decision Layer는 일반 배포와 같은 wheel을 컨테이너 안에서 빌드·설치합니다.
빌드된 UI를 포함하므로 실행 환경에는 호스트 소스나 Node.js가 필요하지 않습니다.
Dockerfile 전용 ignore 파일로 `.env`, 기존 빌드 결과, 고객사 자산을 제외합니다.

두 검증 스크립트는 호스트 포트를 공개하거나 소스를 마운트하지 않습니다.
Heartcube 검증만 전용 내부 네트워크와 일회용 PostgreSQL을 생성하며,
스크립트가 종료될 때 생성한 컨테이너·볼륨·네트워크를 정리합니다.
fixture의 인증과 데이터는 이미지 검증용이며 authentik 통합 검증은 이후 단계입니다.

Heartcube는 메모리 큐와 직접 조회로 운영 모드의 PostgreSQL 집계를 검증했습니다.
이 구성에는 pre-aggregation이 없으며 별도 CubeStore/refresh 서비스가 필요하지 않습니다.
pre-aggregation이나 다중 인스턴스를 추가하면 해당 구성을 별도로 검증해야 합니다.
Heartcube는 운영 모드에서도 `/cubejs/conf/cube.config.js`를 필요로 합니다.
`cube/`의 모델·`cube.py`와 함께 배포합니다.

이미지 파일로 옮길 경우:

```bash
docker image save -o /tmp/decision-layer-poc-images.tar \
  heartcube:poc-a9e8a00 decision-layer:poc-2a67b18
# 대상 서버에서 파일을 전달받은 후
docker image load -i /tmp/decision-layer-poc-images.tar
```

새 빌드에는 새 태그를 사용합니다. 실행 중인 이미지의 태그를 덮어쓰지 않습니다.
베이스 이미지와 의존성은 빌드 시 해석되므로 재빌드가 같은 이미지 ID를 보장하지 않습니다.
이번 검증 이미지 자체를 전달하고, 배포·롤백 시 이미지 ID/digest를 확인합니다.

## 현재 검증과 운영 범위

- 원본 8개 테이블을 모델링한 Cube 11개·View 3개를 실제 DB로 확인했습니다.
- OIDC 로그인, 사용자 attributes의 `cube_groups` 매핑과 원격 MCP OAuth를 검증했습니다.
- MCP 토큰은 기본 1시간이며 자동 갱신은 아직 없습니다.
- admin/guest의 데이터 범위는 같은 PoC 구성입니다. 고객사별 데이터 접근 제한은 별도 구성합니다.
- 실제 접속 정보, 이미지 ID와 검증·백업 기록은 Git 제외 운영 파일에 보관합니다.

shared 모드는 로그인 설정이 모두 있어야 기동합니다. `local`/`demo`로 바꿔 우회하지 않습니다.

## 공개 설정과 운영 기록

이 문서와 RUNBOOK은 설치 절차를 일반 값으로 설명합니다. 실제 SSH 별칭, DB 주소,
계정, 도메인, 운영 이력은 비공개 운영 자산으로 보관합니다. 로컬 `backups/`는 Git에서
제외되며 별도 장치나 비공개 저장소 백업을 대신하지 않습니다. 이전 커밋의 문서에는
운영 정보가 있으므로 공개 푸시 전에 이력도 정리해야 합니다.
