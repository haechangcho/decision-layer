# PoC 배포 구성

새 heartcube와 Decision Layer를 설치할 **구성 초안**입니다.
2026-10-30에 두 `linux/amd64` 이미지를 로컬 빌드하고 임시 컨테이너에서 검증했습니다.
3단계에서 기존 STG `sampledb`의 별도 `journey`, `journey_meta` 스키마에
Complete Journey를 적재하고 독립 SQL 검증을 마쳤습니다. 2026-11-02에 새 Cube 모델·설정과
Decision Layer 로그인(ADR-130)을 추가했습니다. 서버 배포는 이후 단계입니다.
기존 서비스의 Compose·컨테이너·네트워크·볼륨은 사용하지 않습니다.

## 서비스와 포트

| 서비스 | 호스트 포트 → 컨테이너 포트 | 연결 대상 |
|---|---|---|
| 새 heartcube | `${BIND_ADDRESS}:5103 → 4000` | 기존 PostgreSQL `sampledb`의 데모 스키마 |
| 새 Decision Layer | `${BIND_ADDRESS}:5104 → 8000` | 새 `heartcube:4000`. 원격 MCP는 `/mcp` |

| 로컬 이미지 | 검증 결과 |
|---|---|
| `heartcube:poc-20261030` | 네이티브 모듈·Python 설정/인증·운영 모드·임시 PostgreSQL 집계 |
| `decision-layer:poc-20261030-journey2` | 설치 패키지·Web/REST·stdio MCP·OLS 계산·재시작·공유 배포 차단 (이전 빌드) |
| `decision-layer:poc-20261102-auth1` | 위 항목 + shared 모드 로그인 필수·액세스 토큰·원격 MCP 거부 확인 |

이미지는 로컬 Docker에 있으며 레지스트리에 게시하지 않았습니다.
이미지 ID 등 로컬 빌드 기록은 Git 제외 파일 `images.local.json`에 남깁니다.
이 태그는 현재 작업 트리로 만든 PoC 빌드이며 정식 릴리스가 아닙니다.

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

프로젝트 설정·Method·Cube 모델은 읽기 전용으로 연결합니다.
Recipe 디렉터리만 쓰기 가능하며, 컨테이너를 교체해도 파일이 유지됩니다.
Decision Layer 이미지는 UID/GID `10001:10001`로 실행하므로 서버 배포 시
Recipe 디렉터리에 해당 사용자의 쓰기 권한을 준비해야 합니다.
현재 프로젝트는 패키지의 기본 Methods를 사용합니다. 고객사 정의는 이후 추가합니다.

실행 기록은 우선 `decision-layer-data` 볼륨의 SQLite에 저장하는 단일 인스턴스 구성입니다.
`DL_DATABASE_URL`로 기존 PostgreSQL의 **전용 앱 DB**를 선택할 수도 있습니다.
이 경우 Cube의 읽기 계정과 별도의 쓰기 계정을 사용합니다.
PostgreSQL을 선택해도 다중 API 프로세스 실행이 지원되는 것은 아닙니다.
백업 대상은 실행 기록 저장소와 `project/recipes/`이며,
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

Decision Layer 저장소 루트에서 실행합니다. Heartcube 경로는 실제 소스 위치로 바꿉니다.
Heartcube의 기존 Dockerfile을 사용하고, 기존 개발용 Compose는 실행하지 않습니다.

```bash
docker buildx build --platform linux/amd64 --load \
  -t heartcube:poc-20261030 \
  -f ../heartcube/Dockerfile ../heartcube
docker buildx build --platform linux/amd64 --load \
  -t decision-layer:poc-20261030-journey2 \
  -f deploy/poc/Dockerfile.decision-layer .
python3 deploy/poc/smoke_decision_layer.py decision-layer:poc-20261030-journey2
python3 deploy/poc/smoke_heartcube.py heartcube:poc-20261030
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
4단계에서 모델·`cube.py`와 함께 준비합니다.

이미지 파일로 옮길 경우:

```bash
docker image save -o /tmp/decision-layer-poc-images.tar \
  heartcube:poc-20261030 decision-layer:poc-20261030-journey2
# 대상 서버에서 파일을 전달받은 후
docker image load -i /tmp/decision-layer-poc-images.tar
```

새 빌드에는 새 태그를 사용합니다. 실행 중인 이미지의 태그를 덮어쓰지 않습니다.
베이스 이미지와 의존성은 빌드 시 해석되므로 재빌드가 같은 이미지 ID를 보장하지 않습니다.
이번 검증 이미지 자체를 전달하고, 배포·롤백 시 이미지 ID/digest를 확인합니다.

## 다음 단계의 완료 조건

1. **모델:** `cube/`에 journey 모델과 설정 준비 완료. 실제 DB 쿼리와 authentik 로그인은 서버에서 검증.
2. **인증:** Decision Layer 로그인·역할·액세스 토큰·원격 MCP 구현 완료
   ([ADR-130](../../docs/DECISIONS.md#adr-130--application-login-for-a-narrowed-shared-deployment-2026-11-02)).
   실제 authentik 연동은 서버에서 검증.
3. **배포:** 도메인·HTTPS 경로, 파일 권한, 백업·재시작 검증 후 서버 실행.

shared 모드는 로그인 설정이 모두 있어야 기동합니다. `local`/`demo`로 바꿔 우회하지 않습니다.
