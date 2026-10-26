# Cube 연결

회사의 지표와 데이터로 분석하려면 Cube를 연결하세요.

## 프로젝트 실행하기

데모가 실행 중이라면 `Ctrl+C`로 종료한 뒤 실행합니다.

```bash
decision-layer init my_team
cd my_team
decision-layer serve
```

## 연결하기

관리자 화면의 **데이터 연결**을 엽니다.

1. Cube API URL과 인증 정보를 입력합니다.
2. **연결 테스트** 후 저장합니다.
3. **지표**에서 지표와 차원을 확인합니다.

| Cube 위치 | API URL 예시 |
|---|---|
| 내 컴퓨터 | `http://127.0.0.1:4000/cubejs-api/v1` |
| 원격 서버 | `https://your-cube.example/cubejs-api/v1` |
| Decision Layer가 Docker 안에서 실행 중 | `http://host.docker.internal:4000/cubejs-api/v1` |

주소는 Decision Layer 서버에서 접근할 수 있어야 합니다.
실제 Cube는 해당 환경의 사용자 토큰을, 로컬 테스트는 개발용 API secret을 사용합니다.
서버의 인증 설정은 [.env.example](https://github.com/haechangcho/decision-layer/blob/main/.env.example)을 참고하세요.

## 연결되지 않을 때

- **접근 실패**: URL의 `/cubejs-api/v1`, 포트와 네트워크를 확인합니다.
- **401 또는 403**: 토큰의 유효기간과 권한을 확인합니다.
- **지표나 변수가 없음**: Cube 모델 정의와 접근 권한을 확인합니다.

연결을 마쳤다면 [Recipe를 만들거나](recipes.md) [AI 도구를 연결](mcp.md)해 분석하세요.
