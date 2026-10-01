# Semantic API 연결 UX와 기업 인증 검토

검토일: 2026-10-01. 상태: 공식 문서 조사와 권장 설계. 기업 OIDC/OAuth 기능은 아직 구현되지 않았다.

범위 변경: 사용자 요청으로 아래 S2/S3 기업 인증 제안은 현재 개발 계획에서 제외했다. 관련 내용은 조사 기록으로만 보존하며 다음 작업으로 진행하지 않는다. 기존 Cube 인증과 권한 검사는 유지한다.

구현 업데이트: S1의 URL·인증 입력 화면, 자동 탐색 제거, 테스트/실행의 공통 인증 선택을 구현했다(ADR-037). 아래 '현재 코드와 차이'는 조사 당시 상태이며, OIDC 신원 검증·Run 권한과 기업 서비스 계정 항목은 여전히 미구현이다. 실제 인증 Cube의 조회까지는 추가 검증이 필요하다.

## 해결할 사용자 문제

관리자는 자신이 운영하는 semantic API의 주소와 인증을 명시하고, 일반 사용자는 관리자가 연결한 모델을 자신의 권한으로 사용해야 한다. 로컬 주소 자동 탐색은 어떤 서버에 연결되는지 감추므로 기본 경험으로 적합하지 않다. 간결함은 입력을 숨기는 대신 필요한 입력만 보여 주는 것으로 구현한다.

## 다른 제품에서 확인한 패턴

| 참고 | 실제 설정 | 적용할 점 |
| --- | --- | --- |
| [Grafana Prometheus 연결](https://grafana.com/docs/grafana/latest/datasources/prometheus/configure/) | 서버 URL, 인증 방식, 필요한 자격 증명, Save & test. OAuth 사용자 신원 전달도 별도 선택 | 주소와 인증을 기본 화면에 표시하고 연결 결과를 즉시 제공 |
| [dbt Semantic Layer 연동](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works) | Host, Environment, Service Token으로 API 접근 | provider별 필수 연결 정보를 명시. MetricFlow 오픈소스 자체와 dbt 호스팅 API를 동일시하지 않음 |
| [Cube Core 배포 및 인증](https://docs.cube.dev/admin/deployment/core) | JWT/JWKS, issuer, audience 등으로 API 인증 구성. 개발 모드는 인증 검증을 우회할 수 있음 | 로컬 무토큰 응답을 운영 인증 성공의 근거로 사용하지 않음 |

Grafana는 semantic layer 제품은 아니지만 API 데이터 소스 설정 UX의 참고 사례다. dbt의 호스팅 Semantic Layer API 계약을 미래 provider의 일반 계약으로 고정하지 않는다.

## 권장 연결 화면

```text
Cube 연결

Cube API URL  [https://cube.example.com/cubejs-api/v1]
인증 방식     [Access token                         v]
Access token  [**************************************]

[연결 확인]   [저장하고 지표 탐색]
```

- URL은 항상 보인다. 사용자가 입력하거나 환경변수로 지정한 주소만 호출한다. localhost, Docker 서비스 이름 등은 선택 가능한 예시이며 자동 검색하거나 교체하지 않는다.
- 안내는 Decision Layer 서버에서 접근할 주소를 기준으로 한다. Docker에서 localhost는 API 컨테이너 자신을 가리킨다.
- 기본 인증은 사용자가 제공한 access token 전달이다. 토큰은 별도 발급 주체가 발급한다. 만료된 토큰을 문자열만으로 자동 갱신할 수는 없다.
- 인증 없음은 개발 모드가 허용된 배포에서 명시적으로 선택한다. API secret을 통한 서명도 개발용 고급 설정이다. 인증 실패 시 두 방식으로 자동 재시도하지 않는다.
- 기업 OIDC 설정이 완료되면 사용자는 '회사 계정으로 연결'을 선택한다. 아직 구현하지 않은 모드를 작동하는 선택지처럼 노출하지 않는다.
- `/meta` 성공은 카탈로그 접근 확인이다. 실제 조회 성공은 사용자가 지표를 선택해 작은 미리보기를 실행한 뒤 별도로 표시한다.
- 주소/네트워크/TLS 실패, 401 인증 실패, 403 권한 부족, 로그인 HTML 반환, 공개 지표 없음, 실제 조회 실패를 구분한다.
- 검사 후 URL이나 인증을 바꾸면 검사 결과를 무효화한다. 저장은 관리자 권한으로만 하고 일반 사용자는 연결 상태와 자신의 접근 상태를 확인한다.
- 환경변수 우선 원칙은 유지한다. 고정된 필드는 이유를 함께 표시한다. 관리 권한 확인은 로그인 또는 최초 관리자 설정에서 처리하는 것이 목표이며, 현재의 별도 관리자 키는 과도기 구현이다.

## authentik 연동 권장안

[authentik OAuth/OIDC](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)는 discovery/JWKS와 authorization code, PKCE, refresh를 제공한다. 다음은 이 계약과 Cube JWT 설정에 근거한 설계 권장안이며 현재 배포에서 호환성을 검증한 결과는 아니다.

### 직원별 데이터 권한이 필요한 경우

1. 관리자가 authentik OIDC application을 등록하고 discovery URL, client ID, 필요한 client secret 및 callback을 설정한다. Cube용 access token의 대상과 claims를 정한다.
2. 직원은 회사 계정으로 로그인한다. 서버는 검증된 OIDC 라이브러리로 code 교환, state/nonce/PKCE 및 신원 검증을 처리하고 브라우저에는 HttpOnly 세션 쿠키를 사용한다.
3. Cube가 받아들일 audience를 가진 access token만 Cube에 전달한다. 로그인용 ID token이나 Decision Layer 전용 access token을 무조건 전달하지 않는다. 다른 audience가 필요하면 공급자가 지원하는 위임/교환 흐름을 별도 구현한다.
4. Cube는 authentik의 서명 키, issuer, audience, 만료를 검증하고 semantic 모델의 접근 정책에 claims를 반영한다. 서명 검증만으로 행/지표 권한이 저절로 생성되지는 않는다.
5. 토큰 발급·갱신은 서버가 맡고, 실패하면 재로그인을 안내한다. OIDC 신원은 issuer와 subject를 함께 식별자로 사용한다.

### 공용 서비스 계정으로 조회하는 경우

[authentik M2M](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/machine_to_machine)은 client credentials와 서비스 계정 자격 증명을 통한 access token 발급을 지원한다. 배포 버전과 서비스 계정 생성 정책에 따라 설정을 확인해야 한다.

- 관리자가 token endpoint, client ID, 해당 방식의 secret, 필요한 scopes를 설정하면 서버가 access token을 발급받고 만료 전에 다시 발급받는다.
- 데이터 조회는 서비스 계정 권한으로 수행된다. 직원별 Cube 권한 전달과 같은 기능으로 설명하면 안 된다.
- Run에는 실제 요청한 사용자와 Cube에 사용한 서비스 계정을 구분해 기록한다. 공용 자격 증명이 있다고 모든 사용자의 Run을 같은 소유자로 처리하지 않는다.
- 암호화된 secret 또는 외부 secret 참조를 사용한다. 로그·Recipe·Run·Git에는 토큰/secret을 기록하지 않는다.

authentik 관리 API 토큰, app password, OAuth access token은 서로 다르다. 특히 [authentik Proxy Bearer 인증](https://docs.goauthentik.io/add-secure-apps/providers/proxy/header_authentication)은 관리 API 토큰이나 app password를 그대로 Bearer로 받지 않으며, 인증 후 Authorization 헤더도 제거한다. 따라서 프록시를 통과했다는 사실만으로 Cube가 같은 토큰을 검증한다고 가정하지 않는다. 첫 기업 통합은 Cube가 직접 JWT를 검증하는 경로를 권장한다.

## 현재 코드와 차이

- `web/app/sources/page.tsx`: URL 입력이 고급 관리자 설정 안에 있고 자동 연결이 기본이다. URL과 인증을 기본으로 올려야 한다.
- `src/decision_layer/api/app.py`: `connect-local`이 여러 주소를 시도하고 설정을 저장한다. 기업 배포 기본 계약으로 부적절하며 제거 대상이다. 같은 자격 증명을 다른 후보 서버로 보내지 않아야 한다.
- `src/decision_layer/auth.py`: `identify()`는 provider의 discover 성공 후 JWT를 서명 검증 없이 읽는다. Cube 개발 모드/인증 프록시는 이 전제를 깨뜨릴 수 있으므로 기업 사용자 신원과 Run 권한을 이 경로에 의존시키면 안 된다.
- 현재 source의 auth method와 실행 시 자격 증명 선택이 완전히 일치하지 않는다. 검사와 실제 실행은 명시적 인증 정책을 공유해야 한다.
- 현재 API는 별도 source-admin key, 브라우저 탭의 사용자 토큰, 개발용 서명만 제공한다. 회사 로그인, OAuth 자동 갱신, 기업용 공용 서비스 계정 모드는 미구현이다.

## 구현 순서와 완료 기준

| 단계 | 범위 | 사용자 기준 완료 시나리오 |
| --- | --- | --- |
| S1 연결 UX 수정 | URL·명시적 token/dev-none 선택, 자동 주소 탐색 제거, 설정 검사와 실행 자격 증명 통일 | 관리자가 지정한 URL로만 연결하고, 잘못된 토큰이면 다른 인증 방식으로 우회하지 않으며, 지표 탐색·미리보기까지 진행 |
| S2 기업 사용자 인증 | OIDC 서버 세션, claims 검증, source-admin 권한, 사용자별 Cube access token, Run 신원 보완 | authentik의 서로 다른 권한을 가진 두 사용자가 다른 catalog/data를 보고 서로의 비공유 Run에 접근하지 못함. 만료·잘못된 issuer/audience·로그아웃 검증 |
| S3 서비스 계정 | 명시적 M2M 모드, 서버 발급/재발급, secret 저장, 실행자/조회 신원 분리 | 같은 서비스를 쓰는 두 사용자의 Run 소유권이 구분되고, 만료/회전/발급 실패가 조회 결과와 UI에 일관되게 반영 |
| S4 배포 확장 | 실제 요구에 따른 사내 CA, 인증 프록시 계약, 추가 provider별 인증 | HTTPS/authentik을 포함한 재현 가능한 설치 예제로 Web·REST·MCP 동일 권한 동작 확인 |

검증에서는 임의 URL에 credential을 보내는 회귀, 실패 시 무인증 fallback, token 로그 유출, token cache의 사용자 혼용도 포함한다. 사설망 Cube는 정상 사용 사례이므로 localhost 제한만으로 주소 정책을 대신하지 않는다.

## ADR 영향

- ADR-036의 자동 발견 중심 UX는 재검토한다. 명시적인 개발 무인증 허용만 제한적으로 유지하는 방향이다.
- ADR-024/029: 기업 OIDC 신원 검증과 서비스 조회 신원을 분리하는 새 결정이 필요하다. semantic layer의 데이터 권한 소유는 유지한다.
- ADR-033: 관리자 권한을 OIDC 세션에 연결하고, 운영용 secret/갱신 토큰 저장 정책을 추가할 때 보완한다.
- 이번 조사에서는 기존 인증 코드를 변경하지 않았다. S1 이후 단계의 동작이나 보안 검증을 완료로 표시하지 않는다.
