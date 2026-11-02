# dev_mcp PoC 운영 절차

이 문서는 개발 PC에서 `dev_mcp`에 접속하고, 기존 서비스를 유지하면서 PoC를 준비·배포·검증하는 순서를 기록합니다.

## 1. 현재 상태

2026-11-02에 확인한 상태입니다.

| 항목 | 상태 |
|---|---|
| SSH 접속 | `ssh dev_mcp` 별칭 사용. AWS SSM Session Manager를 통한 SSH |
| 서버 | Ubuntu EC2, 내부 주소 `20.0.1.20`, 사용자 `ubuntu` |
| 기존 컨테이너 | `heartcube` (`5101`, `15432`), `heartmcp` (`5102`) 실행 중 |
| 기존 PostgreSQL | 별도 서버 `20.0.1.10:5432`, DB `sampledb` |
| 데모 데이터 | `sampledb.journey`, `sampledb.journey_meta`에 적재 및 SQL 검증 완료 |
| 새 이미지 | 로컬 Docker에 있음 (`heartcube:poc-20261030`, 로그인 기능이 들어간 `decision-layer:poc-20261102-auth1`). 서버로 전달하지 않음 |
| 새 컨테이너 | 아직 `dev_mcp`에 배포하지 않음 |
| Decision Layer 공유 모드 | OIDC 로그인·액세스 토큰·원격 MCP 구현 및 로컬 테스트 완료 (ADR-130). 실제 authentik 로그인은 미검증 |

`dev_mcp` 루트 파일시스템은 96GB 중 약 20GB가 남아 있었습니다. 이는 애플리케이션 서버의 디스크이며 PostgreSQL 서버의 여유 공간과는 별개입니다. 배포 전 `docker system df`와 `df -h`로 다시 확인합니다. 용량 확보를 위해 `docker system prune`이나 볼륨 삭제를 하지 않습니다.

## 2. 구성도와 포트

```text
브라우저 / MCP 클라이언트
       │
       ├── HTTPS 또는 SSH 터널 ── 새 Decision Layer :5104
       │                              │
       │                              └── 새 Heartcube :5103
       │                                      │
       │                                      └── 20.0.1.10:5432 / sampledb
       └── 로그인 ── 기존 STG authentik

기존 Heartcube :5101, HeartMCP :5102는 그대로 유지
```

| 서비스 | 서버 포트 | 컨테이너 포트 | 설명 |
|---|---:|---:|---|
| 기존 Heartcube | 5101 | 4000 | 유지 |
| 기존 Heartcube SQL | 15432 | 15432 | 유지 |
| 기존 HeartMCP | 5102 | 5102 | 유지, 이번 작업 범위에서 수정하지 않음 |
| 새 Heartcube | 5103 | 4000 | 기본 `127.0.0.1` 바인딩. 포트 승인 후 `.env`의 `BIND_ADDRESS=0.0.0.0` |
| 새 Decision Layer | 5104 | 8000 | 같음. 원격 MCP는 같은 포트의 `/mcp` |
| 기존 PostgreSQL | 해당 없음 | 해당 없음 | 별도 서버 `20.0.1.10:5432` 사용 |

현재 Compose는 새 Cube를 `sampledb`의 `journey` 데이터에 연결하도록 작성됐습니다. 고객사에서는 같은 자리에 기존 DM/DW 연결 정보를 넣습니다. 새 서비스의 포트가 localhost에만 바인딩되므로 외부 사용자는 직접 접속하지 못합니다. PoC 임시 확인은 SSH 터널을, 실제 고객 접속은 검증된 HTTPS 프록시/도메인을 사용합니다.

## 3. 개발 PC에서 SSH 접속

개발 PC에서 SSH 개인키를 사용할 수 있도록 세션에 등록합니다. passphrase는 SSH가 요청할 때 로컬 터미널에 입력합니다. 메모 파일이나 채팅에 passphrase를 복사하지 않습니다.

```bash
ssh-add ~/.ssh/id_ed25519
ssh dev_mcp
```

세션당 최초 한 번 `ssh-add`를 수행하면 됩니다. 접속 후 서버가 맞는지, 기존 서비스가 그대로 있는지 확인합니다.

```bash
hostname
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
df -h /
docker system df
```

확인된 호스트 이름은 `ip-20-0-1-20`입니다. 기존 `heartcube`, `heartmcp`가 보여야 합니다. 여기서 기존 컨테이너를 재시작·중지·삭제하지 않습니다.

PostgreSQL 서버 연결도 컨테이너를 띄우기 전에 검사합니다.

```bash
nc -vz -w 3 20.0.1.10 5432
```

실패하면 새 서비스 실행을 진행하지 말고 네트워크 경로와 PostgreSQL 방화벽/허용 주소를 운영자와 확인합니다. DB 비밀번호를 명령행 인자나 SSH 명령 문자열에 넣지 않습니다.

## 4. 개발 PC에서 이미지 준비

먼저 Docker Desktop이 실행되고 현재 사용자가 Docker 소켓에 접근할 수 있어야 합니다. 현재 세션에서는 Docker API가 `permission denied`를 반환해 로컬 태그와 이미지 크기를 다시 확인하지 못했습니다. 배포 전에 아래 조회가 동작하는지 확인합니다.

```bash
docker info
docker image inspect heartcube:poc-20261030
docker image inspect decision-layer:poc-20261102-auth1
```

이미지가 없거나 소스가 바뀌었다면 각각 새 태그로 다시 빌드하고 smoke 검증합니다. Heartcube 소스는 `/Users/hc.cho/Workspace/heartcube`에 있습니다.

```bash
docker buildx build --platform linux/amd64 --load \
  -t heartcube:poc-20261102 \
  -f /Users/hc.cho/Workspace/heartcube/Dockerfile \
  /Users/hc.cho/Workspace/heartcube

docker buildx build --platform linux/amd64 --load \
  -t decision-layer:poc-20261102 \
  -f deploy/poc/Dockerfile.decision-layer .

python3 deploy/poc/smoke_heartcube.py heartcube:poc-20261102
python3 deploy/poc/smoke_decision_layer.py decision-layer:poc-20261102
```

검증 스크립트는 임시 컨테이너/네트워크를 만들었다가 정리합니다. 기존 서비스는 사용하지 않습니다. 검증이 통과한 이미지 태그를 Compose와 아래 전달 명령 양쪽에서 동일하게 사용합니다.

## 5. 인증 구성 (ADR-130)

Decision Layer는 `shared` 모드에서 다음을 지원합니다. `local`이나 `demo`로 바꿔 기동하는 우회는 하지 않습니다.

- authentik OIDC 로그인(PKCE)과 서명된 세션 쿠키. `/health`, `/auth/*` 외 모든 API는 로그인 필요
- Web·REST·MCP 공통 사용자 신원. Run은 본인 것만 조회
- 역할: `dl-poc-admin` → Recipe 작성·게시, `dl-poc-guest` → 분석 실행·게시된 Recipe 조회
- Cube 조회: Decision Layer가 사용자별 짧은 Cube 토큰을 `DL_CUBE_TOKEN_SECRET`으로 서명. 새 Cube는 이 키를 `DECISION_LAYER_TOKEN_SECRET`으로 따로 신뢰
- 원격 MCP: `https://<DL 주소>/mcp`. 브라우저에서 로그인 후 `/auth/tokens`에서 개인 액세스 토큰을 발급해 Claude Code/Codex 설정에 넣음
- shared 모드에서는 Method 편집, HTTP 소스 관리, 서비스 자격증명을 켤 수 없음 (켜면 기동 실패)

authentik 운영자 작업:

1. 그룹 `dl-poc-admin`, `dl-poc-guest` 생성 (새 Cube와 공용)
2. **Decision Layer용 새 OAuth2/OIDC Application** 생성. Cube용과 별개
   - Redirect URI: `https://<DL 주소>/auth/callback` (SSH 터널 확인용은 `http://localhost:5104/auth/callback`)
   - scope mapping: `cube_groups` (id_token에 그룹 이름 배열). Cube 앱과 같은 mapping 사용 가능
   - 서명 키 지정 권장 (RS256). 미지정 시 client secret 기반 HS256도 처리함
3. Issuer, client ID, client secret을 서버 `.env`에 입력

검증하지 못한 것: 실제 authentik 로그인, 실제 DB 쿼리, HTTPS 프록시 뒤 동작. 서버 기동 후 9절에서 확인합니다.

알려진 제한: 세션은 만료(`DL_SESSION_HOURS`, 기본 8시간) 전에 서버에서 강제 종료할 수 없고, 액세스 토큰은 만료(기본 30일)나 폐기 전까지 발급 당시 역할을 유지합니다. authentik 그룹 변경은 다음 로그인부터 반영됩니다.

## 6. 서버 배포 디렉터리와 설정 파일 준비

공유 배포 기능 및 인증 검증을 완료한 뒤 진행합니다. 서버에는 PoC 전용 디렉터리를 새로 만듭니다. 기존 `~/heartcube`, `~/heartmcp`는 건드리지 않습니다.

개발 PC에서 Compose 및 고객사 설정 디렉터리를 복사합니다. 비밀값을 포함할 수 있는 `.env`는 이 tar에 넣지 않습니다.

```bash
tar -C deploy/poc -cf - compose.yaml cube project \
  | ssh dev_mcp 'mkdir -p ~/decision-layer-poc && tar -xf - -C ~/decision-layer-poc'
```

설정 파일의 실제 내용은 배포 대상에 맞게 준비합니다.

- `cube/model/`: `journey` 스키마 모델
- `cube/cube.py`, `cube/cube.config.js`: 새 Cube의 인증 및 사용자 그룹 설정
- `project/decision-layer.yaml`: 프로젝트 이름·기본 Method 설정
- `project/methods/`, `project/recipes/`: 검토·승인된 고객사 분석 자산
- `.env`: 새 이미지 태그, DB 접속, 새 Cube 서명키, authentik 설정, 허용 Host/URL

현재 예시 `.env`는 빈 비밀 항목이 있으므로 그대로는 Compose 설정 검증을 통과하지 않습니다. `.env`는 서버에서 권한 `600`으로 만들고, 비밀번호·client secret·서명키를 터미널 명령 인자, 셸 기록, Git에 넣지 않습니다. 기존 서비스 `.env`를 복사하지 않습니다.

## 7. 새 이미지 전달 및 용량 확인

검증한 이미지만 SSH 표준입력으로 전달합니다. 이미지 크기에 따라 전송 시간이 걸립니다.

```bash
docker save heartcube:poc-20261030 decision-layer:poc-20261102-auth1 \
  | ssh dev_mcp 'docker load'
```

서버에서 태그가 로드됐는지 확인합니다.

```bash
ssh dev_mcp 'docker image ls --format "table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}"'
ssh dev_mcp 'df -h /; docker system df'
```

공간이 부족하면 기존 이미지/볼륨을 임의 삭제하지 말고 운영자와 용량 확장 또는 정리 대상을 결정합니다. PoC 이미지는 기존 태그를 덮어쓰지 않고 버전이 있는 새 태그로 전달합니다.

## 8. 환경 설정 검증 및 기동

`.env`와 Cube/프로젝트 파일이 모두 준비되면 먼저 Compose 문법과 필수값만 검사합니다.

```bash
ssh dev_mcp
cd ~/decision-layer-poc
docker compose --env-file .env -f compose.yaml config --quiet
```

`--quiet`을 사용해 비밀값이 포함될 수 있는 Compose 전체 설정을 화면이나 로그에 출력하지 않습니다. 이 검사는 YAML/변수 치환만 검사하고 DB 접속·로그인 성공을 증명하지 않습니다.

로그인 설정(`DL_OIDC_*`, `DL_PUBLIC_URL`, `DL_SESSION_SECRET`, `DL_CUBE_TOKEN_SECRET`)이 빠지면 Decision Layer는 기동하지 않습니다.

```bash
docker compose --env-file .env -f compose.yaml up -d
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml logs --tail=100 heartcube decision-layer
```

Health 확인:

```bash
curl --fail http://127.0.0.1:5103/readyz
curl --fail http://127.0.0.1:5104/health
```

로그에 비밀번호나 토큰이 찍히지 않는지 살피고, 오류가 나면 새 PoC 서비스만 조사합니다. 기존 서비스 이름이나 전체 Docker 프로젝트에 대해 `down`, `restart`, `rm`, `prune`을 실행하지 않습니다.

## 9. 개발 PC에서 SSH 터널로 확인

서비스가 서버의 localhost 포트에 기동되고, 인증 callback 설정도 터널 주소와 일치하는 경우 개발 PC에서 별도 터미널에 터널을 엽니다.

```bash
ssh -N \
  -L 5103:127.0.0.1:5103 \
  -L 5104:127.0.0.1:5104 \
  dev_mcp
```

그 상태에서 브라우저로 `http://localhost:5103`과 `http://localhost:5104/ui`를 확인할 수 있습니다. OIDC는 redirect URI와 외부 URL이 정확히 일치해야 하므로 localhost 터널용 redirect가 STG authentik 정책에 허용되는지 먼저 확인합니다. 고객 데모의 정식 접속은 HTTPS 도메인과 reverse proxy를 사용하고, 그 주소에 맞는 callback URL을 등록합니다.

확인 순서:

1. `http://localhost:5104/ui` 접속 → authentik 로그인 화면으로 이동하는지
2. `dl-poc-admin` 계정 로그인 → 콘솔 표시, `/me`의 `role`이 `admin`
3. `dl-poc-guest` 계정 로그인 → Recipe 저장이 거부되는지
4. 두 그룹 어디에도 없는 계정 → 접근 거부 화면
5. `/auth/tokens`에서 토큰 발급 → 아래처럼 Claude Code에 등록 후 `list_methods` 호출

```bash
claude mcp add --transport http decision-layer http://localhost:5104/mcp --header "Authorization: Bearer <발급한 토큰>"
```

## 10. 중지·롤백·데이터 보존

PoC만 중지할 때는 서버의 PoC 디렉터리에서 프로젝트 범위를 지정해 실행합니다.

```bash
cd ~/decision-layer-poc
docker compose --env-file .env -f compose.yaml stop
```

컨테이너를 제거해야 할 때도 PoC 프로젝트의 Compose만 대상으로 하고 `-v`를 붙이지 않습니다. `-v`는 Decision Layer 실행 기록 볼륨을 지웁니다.

```bash
docker compose --env-file .env -f compose.yaml down
```

이미지 롤백은 `.env`의 새 서비스 이미지 태그를 직전 검증 태그로 바꾼 뒤 PoC 프로젝트만 재기동하는 방식입니다. `decision-layer-data` 볼륨과 `project/recipes/`를 별도로 백업합니다. `sampledb.journey`와 `sampledb.journey_meta`는 공유 DB에 남아 있으므로 데이터 삭제/정리는 별도 승인과 백업 확인 없이는 하지 않습니다.

## 11. 저장소 변경과 비밀 관리

현재 작업 트리에는 PoC 외 분석 평가 예제, 소스, 테스트의 수정·추가 파일도 함께 있습니다. 배포 전에 전체 변경 사항을 검토하고, 본 PoC에 속하는 파일만 골라 커밋합니다. `deploy/poc/.env`, DB 자격증명, authentik client secret, 서명키, 고객사 모델·Recipe는 공개 Git에 넣지 않습니다.

