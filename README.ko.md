# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [기여 안내](CONTRIBUTING.md)

**분석가의 노하우를 팀과 AI가 함께 쓰는 분석 절차로.**

Decision Layer는 시맨틱 레이어 위에서 동작하는 오픈소스 분석 도구입니다. 분석가는 반복하는 분석 절차를 **Recipe**로 만들고, 팀원과 AI는 같은 지표와 절차로 분석합니다. 실행 결과와 근거는 기록으로 남습니다.

![Cube의 지표를 분석 Recipe로 구성하고 실행 근거를 남기는 Decision Layer](docs/assets/decision-layer-overview.png)

## 어떤 문제를 해결하나요?

시맨틱 레이어에 지표가 정의되어 있어도, 그 지표를 어떻게 분석할지는 여전히 사람의 경험에 달려 있습니다.

예를 들어 "매출이 왜 줄었을까?"라는 질문에 숙련된 분석가는 이전 기간과 비교하고, 상품·지역별 변화를 나눈 뒤, 영향이 큰 항목을 더 살펴봅니다. Decision Layer는 이 절차를 다른 사람도 반복해서 실행할 수 있게 만듭니다.

- **분석 절차를 재사용합니다.** 등록된 분석 방법을 조합해 Recipe로 만들고 버전별로 관리합니다.
- **기존 지표를 그대로 씁니다.** 지표의 정의와 데이터 접근 권한은 Cube에서 관리합니다.
- **웹과 AI에서 같은 분석을 실행합니다.** 웹 앱과 MCP가 같은 실행 엔진을 사용합니다.
- **결과의 근거를 확인합니다.** 각 실행 기록에서 입력, 결과, 쿼리, 검증 내용과 경고를 살펴볼 수 있습니다.

## 어떻게 동작하나요?

| 구성 요소 | 역할 |
| --- | --- |
| **Cube** | 지표 정의, 차원, 조인, 데이터 접근 권한 관리 |
| **Method** | 추이, 항목별 분석, 조건 맞춤 비교 같은 개별 분석 기능 |
| **Recipe** | Method와 지표를 조합한 팀의 분석 절차 |
| **Run** | 실제로 실행한 분석과 그 결과·근거를 담은 기록 |

웹, REST API, MCP는 같은 명세와 Python 실행 엔진을 사용합니다. Recipe는 YAML 파일로 관리하고, Run은 SQLite 또는 PostgreSQL에 저장합니다. AI는 등록된 도구를 선택합니다. Decision Layer 서버에서 LLM을 구동하거나 AI가 만든 분석 코드를 실행하지 않습니다.

상세 구조와 설계 결정은 [아키텍처](docs/ARCHITECTURE.md)와 [ADR](docs/DECISIONS.md)에 정리되어 있습니다.

## 시작하기

Docker와 Compose, 연결할 Cube API가 있으면 됩니다.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
docker compose up -d --build --wait
```

**http://localhost:3000/sources** 에서 **Cube API URL과 access token**을 입력하고 연결을 확인·저장하세요. 내 컴퓨터의 4000번 포트에서 Cube를 실행 중이라면 `http://host.docker.internal:4000/cubejs-api/v1`을 입력하면 됩니다. 연결된 지표를 살펴보고 Recipe를 만드세요. 로컬 실행 설정의 Recipe 편집 키는 `local-recipe-key`입니다.

처음 실행할 때 이미지를 빌드하며, Python과 Node.js는 이미지에 포함됩니다. Recipe와 실행 기록은 Docker 볼륨에 저장됩니다. `docker compose down`으로 종료해도 데이터는 유지됩니다. 기본 구성은 로컬용이며, 공유 서버에는 별도의 관리자 키와 배포 설정을 사용하세요.

포트가 사용 중이면 `WEB_PORT=3010 API_PORT=8010 docker compose up -d --build --wait`로 실행하세요. 아직 Cube가 없다면 [샘플 데이터 데모](examples/ecommerce/README.md)로 시작할 수 있습니다. 소스에서 직접 실행하는 방법은 [기여 안내](CONTRIBUTING.md)에 있습니다.

## AI에서 사용하기

Claude, Codex 등 MCP를 지원하는 클라이언트에 `decision-layer-mcp`를 연결하세요. AI가 지표와 Recipe를 찾고 분석을 실행할 수 있으며, 같은 실행 기록을 웹에서도 확인할 수 있습니다.

질문에 맞는 Recipe가 있으면 우선 사용하도록 안내합니다. Recipe가 없으면 등록된 Method로 분석할 수 있습니다. 토큰은 Cube로 전달되며, 데이터 접근 권한은 Cube의 설정을 따릅니다.

저장소 루트에서 `pip install '.[mcp]'`로 MCP 어댑터를 설치한 뒤, 클라이언트가 `decision-layer-mcp`를 실행하도록 설정하세요. 환경변수 `DL_API_URL=http://localhost:8000`과 `DL_TOKEN`에 Cube access token을 지정합니다. 웹과 MCP에서 같은 실행 기록을 보려면 같은 Cube 사용자로 접속해야 합니다.

## 개발 현황

현재 초기 개발 단계입니다. Cube 연결, Method 실행, Recipe 그래프 편집, 실행 기록 저장을 지원합니다.

앞으로 Recipe 작성 과정을 단순화하고 기본값을 정리할 예정입니다. MCP 실행 기록을 Recipe 그래프 초안으로 만들고 사용자가 검토·승인하는 기능도 계획하고 있으며, 아직 구현되지는 않았습니다.

[Recipe 예제](examples/ecommerce/recipes/) · [Method 구현](src/decision_layer/methods/)

## 기여하기

분석 방법, Recipe 예제, 문서, 사용성 개선에 기여할 수 있습니다. 개발 환경과 기여 절차는 [CONTRIBUTING.md](CONTRIBUTING.md)를 참고하세요.

## 라이선스

[Apache License 2.0](LICENSE).
