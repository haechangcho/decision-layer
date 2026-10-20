# Cube 연결

Decision Layer는 Cube의 REST API에서 지표와 차원을 읽고 데이터를 조회합니다. 지표 정의와 조인은 Cube에서 관리합니다.

## 프로젝트 실행하기

[Decision Layer를 설치한 환경](quickstart.md)에서 팀 프로젝트를 만들고 실행합니다.
데모가 실행 중이라면 `Ctrl+C`로 종료한 뒤 진행하세요.

```bash
decision-layer init my_team
cd my_team
decision-layer serve
```

## 연결 정보 입력하기

관리자 화면의 **데이터 연결**을 엽니다.

1. Cube API URL과 인증 방식을 입력합니다.
2. **연결 테스트**로 접근 여부를 확인하고 저장합니다.
3. **지표**에서 사용할 지표와 차원이 보이는지 확인합니다.

| Cube 위치 | API URL 예시 |
|---|---|
| 같은 컴퓨터 | `http://127.0.0.1:4000/cubejs-api/v1` |
| 원격 서버 | `https://your-cube.example/cubejs-api/v1` |
| Decision Layer가 Docker 안에서 실행되는 경우 | `http://host.docker.internal:4000/cubejs-api/v1` |

주소는 Decision Layer 서버에서 접근할 수 있어야 합니다. 컨테이너 안의 `localhost`는 그 컨테이너 자신입니다.

## 인증

운영 중인 Cube는 해당 환경에서 발급한 사용자 토큰을 사용합니다. 개발용 API secret과 샘플 인증은 로컬 테스트에 사용합니다.

저장한 인증 정보는 암호화되며 환경변수 설정이 우선합니다. 연결 저장에 필요한 관리자 설정은 [.env.example](https://github.com/haechangcho/decision-layer/blob/main/.env.example)을 참고하세요.

## 연결되지 않을 때

| 증상 | 확인할 내용 |
|---|---|
| 서버에 접근할 수 없음 | URL의 `/cubejs-api/v1`, 포트와 네트워크 |
| 401 또는 403 | 토큰의 유효기간과 접근 권한 |
| 지표가 보이지 않음 | 배포한 Cube 모델과 사용자의 모델 접근 권한 |
| 필요한 날짜나 변수가 없음 | Cube에 해당 정의가 있는지 확인 |

연결한 데이터는 [Recipe](recipes.md)와 [AI 도구](mcp.md)에서 사용할 수 있습니다.
