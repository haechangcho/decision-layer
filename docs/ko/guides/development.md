# 로컬 개발 환경

Method 개발은 [첫 Method 개발](methods.md)부터 시작하세요.
웹·API를 수정하려면 Python 3.11 이상과 Node.js 22가 필요합니다.
아래 명령은 모두 저장소 루트에서 실행합니다.

## 설치

```bash
make setup
make setup-web
```

## API와 웹 실행

한 터미널에서 API를 실행합니다.

```bash
make api
```

다른 터미널에서 웹을 실행합니다.

```bash
make web
```

웹은 **http://localhost:5210**, REST API 문서는 **http://localhost:8000/docs**입니다.
Docker 샘플의 웹 포트는 3000입니다.

소스 연결 없이도 API는 시작됩니다. 실제 분석에는 [Cube](cube.md)나
[dbt Semantic Layer](dbt.md)를 연결하세요. Run은 기본적으로 로컬 SQLite에 저장됩니다.
Recipe 파일을 저장하려면 `DL_RECIPES_DIR=./recipes make api`로 실행하세요.

8000 포트를 이미 사용 중이라면 포트를 바꿉니다.

```bash
.venv/bin/python -m uvicorn decision_layer.api.app:app --reload --port 8001
DL_API_URL=http://localhost:8001 npm --prefix web run dev
```

두 명령은 각각 다른 터미널에서 실행합니다. [MCP 연결](mcp.md)도 같은 API 포트로 바꾸세요.

::: details 샘플 데이터 연결 (선택)
`examples/complete-journey/`에서 데이터 서비스만 실행합니다.

```bash
docker compose -p decision-layer-cube up -d --build --wait postgres import cube
```

샘플 전체가 이미 실행 중이라면 같은 폴더에서 `docker compose -p decision-layer-cube stop api web`으로 샘플 API·웹의 포트를 비우세요. 다른 서비스는 종료하지 않습니다.

저장소 루트로 돌아와 샘플에 연결된 API를 실행합니다.

```bash
mkdir -p data examples/complete-journey/recipes
CUBE_API_URL=http://localhost:4000/cubejs-api/v1 \
CUBE_INSTANCE=journey \
CUBE_API_SECRET=local-example-secret-change-me-0123456789 \
DL_ALLOW_SERVICE_CREDENTIALS=true \
DL_RECIPES_DIR=examples/complete-journey/recipes \
DL_DATABASE_URL=sqlite:///./data/journey-development.db \
  .venv/bin/uvicorn decision_layer.api.app:app --reload --port 8000
```

소스의 포트를 변경했다면 실제 포트를 입력하세요. 웹은 앞의 명령으로 실행합니다. `examples/complete-journey/cube/model/`의 모델은 소스 컨테이너에 직접 마운트됩니다. 예제의 `.env`가 적용되도록 Compose 명령은 예제 폴더에서 실행하세요.

샘플 PostgreSQL에는 원본 데이터가 저장됩니다. 직접 실행한 API는 별도 SQLite DB를 사용하므로 컨테이너 API의 Run 기록을 자동으로 공유하지 않습니다. Recipe는 지정한 폴더의 YAML 파일입니다. 로컬 데이터와 인증 정보는 커밋하지 마세요.

dbt 개발은 기존 dbt Semantic Layer 환경에 [공식 API로 연결](dbt.md)하세요. 어댑터 계약 테스트는 GraphQL 응답을 모의하며, 실제 연동 검증에는 dbt 환경과 인증 정보가 필요합니다.
:::

## 변경 확인

```bash
make test
npm --prefix web run typecheck
npm --prefix web run build
```

문서를 수정했다면 저장소 루트에서 `npm ci`, `npm run docs:build`를 실행하세요.
브라우저·실제 연동 검사는 [테스트](testing.md), 코드 위치는 [아키텍처](../ARCHITECTURE.md),
PR 제출은 [기여 가이드](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)를 참고하세요.
