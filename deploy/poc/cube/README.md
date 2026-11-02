# Cube 설정 위치

이 디렉터리는 새 heartcube의 `/cubejs/conf`에 읽기 전용으로 연결됩니다.

- `model/`: `journey` 스키마 데모 semantic model (cube 8개, view 3개).
  `src/decision_layer/demo/assets/journey/cube/model`을 그대로 복사했습니다.
- `cube.py`: JWT 검증. `CUBEJS_API_SECRET`(Cube 웹앱)이나 `DECISION_LAYER_TOKEN_SECRET`
  (Decision Layer 로그인 사용자, ADR-130)으로 서명한 토큰만 받고, `sub`와
  `cubeGroups`(또는 `cube_groups`)가 없으면 거부합니다. hc-web이 없으므로
  `INTERNAL_TOKEN_SECRET`은 받지 않습니다.
- `cube.config.js`: 웹앱 로그인 그룹과 메뉴. `dl-poc-admin` → admin,
  `dl-poc-guest` → guest만 로그인할 수 있습니다. 데이터 조회 범위는 두 역할이 같고
  메뉴만 다릅니다. `hc-analytics` 메뉴는 Decision Layer UI로 연결됩니다.
- DB 연결과 비밀값: 상위 `.env`에서 컨테이너 환경변수로 전달합니다.

기존 heartcube의 모델과 비밀값은 복사하지 않았습니다. `cube.py`는 기존 파일에서
hc-web 토큰 허용 부분만 뺐습니다. 설정 파일과 모델은 이 공개 저장소에서 기본적으로
Git 제외됩니다. 고객사별 자산의 버전 관리는 별도 비공개 저장소에서 합니다.

## 로컬 검증 (2026-11-02, `heartcube:poc-20261030`)

DB 없이 컨테이너를 띄워 `/cubejs-api/v1/meta`로 확인했습니다.

- admin, guest 토큰 모두 cube 8개와 view 3개(`campaign_analysis`, `campaign_panel`,
  `retail_transactions`)가 컴파일되어 보입니다.
- 토큰 없음, 그룹 없음, 다른 키로 서명한 토큰은 `check_auth`에서 거부됩니다.

검증하지 못한 것: 실제 DB 쿼리, authentik 로그인.

## authentik 준비 (운영자 작업)

1. 그룹 `dl-poc-admin`, `dl-poc-guest`를 만들고 PoC 사용자를 넣습니다.
2. 새 OAuth2/OIDC Provider와 Application을 만듭니다. 기존 Cube 앱을 재사용하지 않습니다.
3. 웹앱은 `openid profile email cube_groups` scope를 요청합니다. scope 이름이 `cube_groups`이고
   id_token에 `cube_groups` claim(사용자의 그룹 이름 배열)을 넣는 scope mapping을 연결합니다.
   웹앱은 `groups`가 아니라 `cube_groups`만 읽습니다. 기존 Cube 앱의 mapping과 같은 방식입니다.
4. Redirect URI를 새 Cube 주소의 `/auth/callback`으로 등록하고, 같은 값을
   `.env`의 `HEARTCUBE_OIDC_REDIRECT_URI`에 넣습니다.
