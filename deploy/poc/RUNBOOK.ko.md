# PoC 설치 운영 절차

이 문서는 승인된 서버에 새 Heartcube와 Decision Layer를 설치하는 공통 절차입니다.
실제 접속 정보와 환경별 진행 기록은 비공개 운영 기록으로 관리합니다.

## 1. 배포 전 준비

- 운영자가 승인한 SSH 별칭, PostgreSQL 연결 정보와 읽기 계정
- Cube와 Decision Layer 각각의 HTTPS 도메인 및 프록시/로드밸런서 라우팅
- authentik의 앱 2개, 그룹과 테스트 사용자
- 검증된 `linux/amd64` 이미지, Cube 모델과 인증 설정, 프로젝트 자산
- 컨테이너 이미지와 실행 기록을 보관할 디스크 공간

새 Compose 프로젝트 이름은 `decision-layer-poc`입니다. 기존 서비스의 디렉터리,
Compose 프로젝트, 네트워크와 볼륨은 재사용하지 않습니다. 새 포트는 기본 5103/5104입니다.

## 2. SSH 접속과 서버 확인

아래 환경변수는 개발 PC에서 승인받은 실제 값으로 설정합니다. 예시 문자열은 실행 전에 바꿉니다.
SSH 키와 SSO/SSM 인증은 해당 조직의 접속 절차를 따릅니다.

```bash
export POC_SSH_HOST='<approved-ssh-alias>'
ssh "$POC_SSH_HOST"
```

접속한 서버에서 운영자에게 받은 호스트 정보와 기존 서비스 목록을 대조합니다.

```bash
hostname
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'
df -h /
docker system df
```

이미지 크기, 다운로드 중 임시 공간과 실행 기록 증가량을 함께 고려합니다.
용량 확보를 위해 기존 이미지·볼륨에 `prune`을 실행하지 않습니다.
PostgreSQL 네트워크 연결은 서버에서 확인합니다.

```bash
nc -vz -w 3 <warehouse-host> <warehouse-port>
```

네트워크 확인 뒤 승인된 계정으로 DB 로그인과 `journey` 조회 권한을 확인합니다.
비밀번호는 비공개 설정 파일이나 승인된 자격증명 관리 수단으로 전달합니다.

## 3. PoC 전용 브랜치에서 계속 수정하고 이미지 빌드

두 저장소의 장기 PoC 브랜치는 **`poc/deployment`**입니다. 이 PoC의 후속 개선은
해당 브랜치에 쌓습니다. 새 버전마다 브랜치를 만들거나 일반 개발 브랜치로 자동 병합하지 않습니다.
이전 기능 브랜치는 보존합니다. 현재 검증 기준은 `versions.json`을 참조합니다.

개발 PC의 DL 저장소 루트에서 두 저장소가 PoC 브랜치인지 확인합니다.
Heartcube가 형제 디렉터리가 아니면 아래 경로와 빌드 도구의 `--source`를 맞춥니다.

```bash
git branch --show-current
git -C ../heartcube branch --show-current
git status --short
git -C ../heartcube status --short
```

같은 PoC 브랜치에서 수정·테스트·커밋한 뒤, 변경한 프로그램을 빌드합니다.
`--plan`은 Docker 없이 브랜치·미커밋 상태를 확인하고 빌드 계획만 출력합니다.

```bash
python3 deploy/poc/build_image.py heartcube --plan
python3 deploy/poc/build_image.py decision-layer --plan
python3 deploy/poc/build_image.py heartcube
python3 deploy/poc/build_image.py decision-layer
```

도구는 `poc/deployment`만 허용하고 추적 파일의 미커밋 변경을 거부합니다.
커밋 소스를 `git archive`로 추출해 `linux/amd64`로 빌드하고, 이미지에 커밋과
PoC 브랜치 label을 기록합니다. 이미지 태그는 `heartcube:poc-<commit>` 또는
`decision-layer:poc-<commit>`이며 기존 로컬 태그를 덮어쓰지 않습니다.
빌드 기록은 `builds/*.local.json`으로 저장하며, 검증/배포 완료를 자동 주장하지 않습니다.

빌드한 태그로 아래 검증 중 해당하는 것을 실행합니다.

```bash
python3 deploy/poc/smoke_decision_layer.py decision-layer:poc-<새커밋>
python3 deploy/poc/smoke_heartcube.py heartcube:poc-<새커밋>
```

실제 authentik·DB·HTTPS 검증은 서버에서 추가로 합니다. 새 이미지와 이전 이미지를 보관하고
`.env`의 해당 이미지 태그를 갱신한 뒤 필요한 서비스만 교체합니다. 예를 들어 DL만 갱신할 때:

```bash
docker compose config --quiet
docker compose up -d --no-deps --wait decision-layer
```

일반 개발용 Heartcube Compose·소스 배포 절차와 혼용하지 않습니다.
모델·설정만 바뀌면 백업·대상 파일 반영·Cube 적용/필요한 재시작·권한과 집계 검증으로 진행합니다.
브랜치 전환이나 빌드 도구는 실행 중인 서버, 기존 `.env`, 모델, DB 볼륨을 변경하지 않습니다.

## 4. 모델과 운영 자산 보관

- `cube/model/`: 승인된 semantic model
- `cube/cube.py`, `cube/cube.config.js`: 토큰 검증, 로그인 그룹과 메뉴 설정
- `project/decision-layer.yaml`, `methods/`, `recipes/`: 프로젝트 자산
- `.env`: 환경별 주소·키·자격증명 (권한 600)

이 파일 중 고객사 설정과 실제 비밀값은 공개 저장소에서 제외됩니다.
비밀값을 제외한 모델·설정은 비공개 운영 저장소에서 버전 관리하고, 비밀값은 별도 관리합니다.
`backups/`의 로컬 스냅샷은 복사본과 해시 manifest를 보관하지만 같은 PC에 있어
독립적인 복구 백업을 대신하지 못합니다. 배포 전에 외부 비공개 보관 위치를 준비합니다.

## 5. authentik와 주소 설정

Cube용과 Decision Layer용 OAuth2/OIDC Application을 각각 준비합니다.

| 항목 | Cube | Decision Layer |
|---|---|---|
| callback | `https://<cube-domain>/auth/callback` | `https://<dl-domain>/auth/callback` |
| SSH 터널 검증용 callback | 필요하면 localhost 주소도 등록 | `http://localhost:5104/auth/callback` |
| scope mapping | id_token의 `cube_groups` 배열 | 같은 그룹 mapping 사용 가능 |

기본 역할 그룹은 `dl-poc-admin`, `dl-poc-guest`입니다. 각 역할과 그룹 밖 테스트 계정을 준비합니다.
PoC는 실제 그룹 가입 대신 사용자 attributes의 `cube_groups` 배열을 권한의 기준으로 사용합니다.
두 앱에 연결한 scope mapping과 앱 접근 정책이 모두 이 속성을 읽어야 합니다.
예: `cube_groups: [dl-poc-admin]`. 속성 변경은 다음 로그인부터 적용됩니다.
Cube는 두 역할에 같은 데이터 조회 범위를 주며, DL의 admin만 Recipe를 작성·게시합니다.
세션은 기본 8시간, 개인 토큰은 기본 30일이고, 토큰은 발급 당시 역할을 유지합니다 (ADR-130).

`.env.example`을 별도 `.env`로 복사해 필수값을 채웁니다. 기존 `.env`는 덮어쓰지 않습니다.

```bash
cd deploy/poc
test -e .env || (umask 077 && cp .env.example .env)
chmod 600 .env
```

- `WAREHOUSE_*`: 승인된 PostgreSQL/DM/DW 연결
- `HEARTCUBE_OIDC_*`: 새 Cube용 issuer·client·callback
- `DL_OIDC_*`: 새 Decision Layer용 issuer·client
- `DL_PUBLIC_URL`: 브라우저에서 사용하는 DL 주소 (callback의 기준)
- `DL_WEB_URL`: 같은 주소의 `/ui/`; Cube 메뉴의 `HC_ANALYTICS_URL`도 일치
- `DL_HTTP_ALLOWED_HOSTS`: 최종 도메인과 내부 요청에 필요한 host
- `HEARTCUBE_API_SECRET`, `DL_SESSION_SECRET`, `DL_CUBE_TOKEN_SECRET`: 서로 다른 새 랜덤 키
- `HEARTCUBE_IMAGE`, `DECISION_LAYER_IMAGE`: 검증한 커밋 태그 또는 digest
- `BIND_ADDRESS=127.0.0.1`: 첫 서버 검증은 localhost 바인딩

로그인 설정이 빠지거나 shared에서 서비스 자격증명·Method 편집·HTTP 소스 관리를 켜면
기동이 실패합니다. 자세한 변수는 `.env.example`, 인증 정책은 ADR-130을 참조합니다.

## 6. 파일과 이미지 전달

개발 PC의 저장소 루트에서 실행합니다. 설정 디렉터리에는 배포할 승인본만 둡니다.
`.env`와 백업은 아래 tar에 포함하지 않습니다. Recipe 디렉터리가 이미 운영 중이면 덮어쓰기 전에
별도 백업과 변경 목록을 확인합니다.

```bash
COPYFILE_DISABLE=1 tar -C deploy/poc -cf - compose.yaml cube project \
  | ssh "$POC_SSH_HOST" 'mkdir -p ~/decision-layer-poc && tar -xf - -C ~/decision-layer-poc'
docker save heartcube:poc-a9e8a00 decision-layer:poc-68258ed \
  | ssh "$POC_SSH_HOST" 'docker load'
```

서버의 전용 디렉터리에 `.env`를 권한 600으로 별도 준비합니다.
Decision Layer 컨테이너는 UID/GID `10001:10001`로 실행하므로 **PoC의** `project/recipes/`에 쓰기 권한을 부여합니다.
프로젝트·인증 설정은 읽기 전용이며 Cube 모델만 Draft/Git 초기화를 위해 쓰기 가능합니다.
이미지 revision/ID도 기록과 대조합니다.

## 7. 서버 기동

서버에서 실행합니다. 전체 `config` 출력에는 비밀값이 포함될 수 있으므로 `--quiet`을 사용합니다.

```bash
cd ~/decision-layer-poc
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml up -d
docker compose --env-file .env -f compose.yaml ps
curl --fail http://127.0.0.1:5103/readyz
curl --fail http://127.0.0.1:5104/health
```

문법·health 성공은 로그인·DB 쿼리 성공을 보장하지 않습니다. 오류 로그는 PoC 서비스만 조회합니다.

```bash
docker compose --env-file .env -f compose.yaml logs --tail=100 heartcube decision-layer
```

## 8. SSH 터널 확인

개발 PC에서 별도 터미널로 실행합니다. 해당 localhost callback을 authentik에 등록하고,
검증에 사용하는 `DL_PUBLIC_URL`과 Cube redirect 설정을 일치시킵니다.

```bash
ssh -N -L 5103:127.0.0.1:5103 -L 5104:127.0.0.1:5104 "$POC_SSH_HOST"
```

브라우저에서 `http://localhost:5103`, `http://localhost:5104/ui/`로 확인합니다.

1. Cube 로그인·모델 조회·실제 집계 쿼리 성공, 데모 매출 기준값 `8,057,463.08` 대조
2. DL admin·guest 로그인과 `/me` 역할 확인, 그룹 밖 계정 거부
3. guest의 Recipe 작성·게시 거부 및 다른 사용자 Run 접근 거부
4. MCP 클라이언트에 HTTPS `/mcp` URL 등록 후 OAuth 로그인·연결 승인으로 도구 호출
5. 분석 Run 실행·결과 저장, 토큰 폐기 후 접근 거부

원격 MCP는 OAuth 자동 로그인을 지원합니다. `/mcp` 주소를 클라이언트에 등록하고
authentik 로그인 뒤 연결을 승인합니다. 기존 DL OIDC 앱과 `/auth/callback`을 재사용합니다.
개인 토큰은 보조 수단으로 유지합니다. `DL_MCP_REDIRECT_HOSTS`에는 승인한 클라이언트의
callback 호스트만 넣습니다. 토큰은 기본 1시간이며 자동 갱신 없이 만료 시 재로그인합니다.
프록시는 `/.well-known/*`, `/authorize`, `/token`, `/register`, `/revoke`, `/oauth/*`도 전달해야 합니다.

## 9. HTTPS 경로와 운영 확인

프록시/로드밸런서의 upstream 주소와 허용 경로를 확인합니다. 서버 밖에서 연결해야 한다면
승인된 포트에 한해 `BIND_ADDRESS=0.0.0.0`으로 조정하고 upstream에서의 접근 범위를 확인합니다.
최종 HTTPS 도메인에 맞춰 public URL, allowed hosts, callback과 Cube 메뉴를 함께 바꾸고
위 로그인·쿼리·MCP 흐름을 다시 확인합니다.

실행 기록 볼륨과 `project/recipes/`를 백업하고 재시작·복구를 확인합니다. 서비스만 중지할 때:

```bash
cd ~/decision-layer-poc
docker compose --env-file .env -f compose.yaml stop
```

컨테이너를 제거할 때는 같은 디렉터리와 Compose를 대상으로 `down`을 사용하며 `-v`는 붙이지 않습니다.
이미지 롤백 전에는 앱 저장 형식의 호환 여부를 확인하고 저장소를 백업합니다.
이미지 태그만 되돌리는 것으로 스키마 변경까지 되돌아가지는 않습니다.
공유 PostgreSQL의 데모 스키마 삭제는 별도 데이터 정리 작업으로 취급합니다.

## 10. 공개 푸시 전 확인

운영 기록은 비공개로 보관합니다. 이전 커밋에 남아 있는 내부 정보는 현재 파일을 수정해도
Git 이력에 남으므로 공개 푸시 전에 정리합니다. 실제 `.env`, 서명키와 client secret,
고객사 모델·Recipe 및 로컬 백업은 공개 Git에 추가하지 않습니다.
