# 개발 환경과 테스트

팀의 분석 함수를 추가하려면 [프로젝트에 등록하기](method-projects.md)를 먼저 읽으세요.
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

## 수정할 코드 찾기

[코드 구조](../ARCHITECTURE.md)에서 실행 흐름과 모듈별 책임을 확인하세요. 실행 규칙은 Python 공통 코드에서 수정하며 Web, REST와 MCP에 별도 계산을 추가하지 않습니다.

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
npm run docs:test
npm run docs:build
```

화면 변경은 개발 서버를 켠 상태에서 확인합니다.

```bash
cd web
npx playwright install chromium
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5210 npm run test:e2e
```

화면 테스트는 API 응답을 대체합니다. 실제 데이터 연결은
[Complete Journey 예제](https://github.com/haechangcho/decision-layer/tree/main/examples/complete-journey)로 검증하세요.

## 변경 제출하기

`make format-methods`로 Method 코드를 정리하고 관련 테스트 결과를 PR에 적습니다.
화면 변경에는 스크린샷을, 분석 변경에는 입력과 기대 결과를 포함하세요.
문제 보고와 리뷰 기준은 [CONTRIBUTING.md](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)에 있습니다.
