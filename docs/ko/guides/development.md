# 제품 개발에 기여하기

팀의 분석 함수를 추가하려면 [Method 만들기](methods.md)를 먼저 읽으세요.
이 문서는 Decision Layer 자체의 실행 코드나 화면을 수정하는 개발자를 위한 안내입니다.
Python 3.11 이상과 Node.js 22가 필요합니다.

## 설치하고 실행하기

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
make setup
make setup-web
```

API와 화면은 각각 다른 터미널에서 실행합니다.

```bash
make api
```

```bash
make web
```

화면은 `http://localhost:5210`, API 문서는 `http://localhost:8000/docs`에서 엽니다.
실제 조회는 [Cube 연결](cube.md)이 필요합니다. 샘플 체험만 하려면
[설치하고 시작하기](quickstart.md)의 `decision-layer demo`를 사용하세요.

## 코드 위치

```text
src/decision_layer/
├── methods/       # Method registration, input contracts and calculations
├── recipes/       # Reusable analysis procedures
├── runs/          # Execution, authorization and recorded evidence
├── semantic/      # Cube connection and canonical queries
├── api/           # REST API
├── mcp/           # AI tools using that API
└── demo/          # Installed sample resources and launcher
web/
├── app/           # Routes
├── features/      # Method, Recipe and Run screens
└── components/    # Shared UI
docs/              # Guides and the bilingual Method notebook
examples/          # Authoring tutorial, complete project and product demos
tests/             # Unit, API, provider and tutorial checks
└── support/       # Shared fixtures and known-answer cases
```

실행 규칙은 Python 공통 코드에서 수정합니다. Web, REST와 MCP는 같은 실행 모델을 사용합니다.
상세 책임은 [아키텍처](../ARCHITECTURE.md)에 있습니다.
프론트엔드의 빌드 결과는 `src/decision_layer/static/`에 생성되며 직접 수정하지 않습니다.

변경 전에 저장소의 `AGENTS.md`, `docs/PRODUCT_CONTEXT.md`, `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md`를 읽으세요. 설계가 바뀌면 결정 기록도 갱신합니다.

## 테스트 {#tests}

변경과 관련된 테스트를 먼저 실행한 뒤 전체 검사를 진행합니다.

```bash
.venv/bin/python -m pytest -q tests/unit/test_method_project.py
make test
npm --prefix web run typecheck
npm --prefix web run build:console
npm ci
npm run docs:build
```

노트북과 완성 프로젝트는 `tests/examples/`, 공통 입력과 실패 사례는 `tests/support/`에서 검증합니다.
선택적 통계 의존성이 필요한 검사는 패키지가 없으면 건너뜁니다. 통계 CI는
`tests/requirements-statistics.txt` 환경에서 별도로 실행합니다.

화면 변경은 개발 서버를 켠 상태에서 확인합니다.

```bash
cd web
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

기본 화면 검사는 API 응답을 대체합니다. 실제 Cube 연결 검증은
[Complete Journey 예제](https://github.com/haechangcho/decision-layer/tree/main/examples/complete-journey)의 안내를 따르세요.
설치 패키지 검사는 `scripts/smoke_distribution.py`, 실제 설치형 데모 검사는
`scripts/smoke_demo.py`가 담당하며 CI에서도 실행합니다.

## 변경 제출하기

`make format-methods`로 Method 코드를 정리하고 관련 테스트 결과를 PR에 적습니다.
화면 변경에는 스크린샷을, 분석 변경에는 입력과 기대 결과를 포함하세요.
문제 보고와 리뷰 기준은 [CONTRIBUTING.md](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)에 있습니다.
