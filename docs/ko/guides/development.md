---
title: 로컬 개발 환경
description: API와 웹을 직접 실행하고 샘플 데이터에 연결합니다.
---

# 로컬 개발 환경

Python 3.11 이상, Node.js 22를 사용합니다. 실제 샘플 데이터까지 실행하려면 Docker와 Compose가 필요합니다. Docker만으로 제품을 실행하려면 [빠른 시작](../index.md)을 참고하세요.

## 의존성 설치

저장소 루트에서 Python 환경을 준비합니다.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

`web/` 폴더에서 웹 의존성을 설치합니다.

```bash
npm ci
```

## API 실행

저장소 루트에서 실행합니다.

```bash
mkdir -p data recipes
DL_RECIPES_DIR=./recipes DL_DATABASE_URL=sqlite:///./data/development.db \
  .venv/bin/uvicorn decision_layer.api.app:app --reload --port 8000
```

데이터 소스를 연결하지 않아도 API를 시작할 수 있습니다. `http://localhost:8000/docs`에서 REST 계약을, `/health`에서 상태를 확인하세요. 실제 분석 전에는 웹에서 소스를 연결해야 합니다.

## 웹 실행

다른 터미널의 `web/` 폴더에서 실행합니다.

```bash
DL_API_URL=http://localhost:8000 npm run dev
```

`http://localhost:5210`을 여세요. 웹은 요청을 API로 전달하며 동일한 분석 엔진을 사용합니다. 8000 포트를 바꿨다면 웹의 `DL_API_URL`과 [MCP 설정](mcp.md)도 함께 바꾸세요.

## 샘플 데이터 연결

`examples/complete-journey/`에서 데이터 서비스만 실행합니다.

```bash
docker compose up -d --build --wait postgres import cube
```

샘플 전체가 이미 실행 중이라면 같은 폴더에서 `docker compose stop api web`으로 샘플 API·웹의 포트를 비우세요. 다른 서비스는 종료하지 않습니다.

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

dbt 개발 환경은 예제 폴더에서 대신 다음 명령으로 시작합니다.

```bash
docker compose -f compose.yaml -f compose.dbt.yaml up -d --build --wait postgres import dbt-setup metricflow
```

저장소 루트에서 API를 실행할 때는 위 Recipe·DB 설정과 함께 `DL_DEFAULT_SOURCE_PROVIDER=metricflow`, `DL_DEFAULT_METRICFLOW_URL=http://localhost:4100`, `DL_DEFAULT_METRICFLOW_INSTANCE=journey`, `METRICFLOW_AUTH_METHOD=none`, `DL_ALLOW_SERVICE_CREDENTIALS=true`를 사용하세요. 기존 연결이 기본값보다 우선하므로 새 기본 연결을 테스트할 때는 별도의 Run DB를 사용합니다. SQL과 YAML은 `examples/complete-journey/dbt/models/`에 있습니다. 수정 후 같은 Compose 파일로 `dbt-setup`을 빌드·실행하고 `metricflow`를 다시 생성하세요. 자세한 내용은 [MetricFlow 가이드](metricflow.md)에 있습니다.

## 코드 위치

| 담당 영역 | 위치 |
| --- | --- |
| 공통 모델 | `src/decision_layer/core/models.py` |
| REST API | `src/decision_layer/api/app.py` |
| MCP 어댑터 | `src/decision_layer/mcp/server.py` |
| Method와 레지스트리 | `src/decision_layer/methods/` |
| Recipe 작성·저장 | `src/decision_layer/recipes/` |
| Run 실행·저장 | `src/decision_layer/runs/` |
| 웹 경로와 공통 UI | `web/app/`, `web/components/` |

다음 단계: [변경 테스트](testing.md), [Method 기여](methods.md), [기여 절차](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md).
