# Chinook: 여러 테이블로 구성한 분석 예제

[English](README.md) | [한국어](README.ko.md)

음원 판매점을 예로 **11개 테이블의 관계와 서로 다른 데이터 단위**를 확인할 수 있습니다. 고객, 청구서, 구매 항목, 음원, 장르, 앨범, 아티스트를 Cube로 연결하고 같은 지표를 웹과 MCP에서 분석합니다.

출처는 [Chinook Database 1.4.5](https://github.com/lerocha/chinook-database/releases/tag/v1.4.5)입니다. 공식 데이터를 내려받아 체크섬을 확인한 뒤 적재합니다. 음원 목록 일부는 실제 라이브러리에서 왔지만 고객과 거래는 예시용으로 생성되었습니다. 실제 기업의 성과나 AI 정확도 향상을 입증하는 데이터는 아닙니다. [사용 허가와 출처](NOTICE.md), 실제 거래 기반 [Online Retail II 예제](../online-retail/README.md)도 참고하세요.

## 실행

Docker와 Compose가 설치된 환경에서 예제 폴더로 이동해 실행합니다.

```bash
cd examples/chinook
docker compose up -d --build --wait
```

**http://localhost:3000/catalog** 에서 지표를 확인하세요. DB 적재와 Cube 연결은 자동으로 설정됩니다. 별도 토큰을 만들 필요는 없습니다. 처음에는 이미지를 빌드하고 약 1.8 MB의 원본 데이터를 내려받습니다.

| 구성 | Docker 이미지 | 기본 호스트 포트 | 컨테이너 간 주소 |
| --- | --- | --- | --- |
| 예제 데이터 DB | `postgres:16.4` | `5433` | `postgres:5432` |
| Cube | `cubejs/cube:v1.6.25` | `4000` | `http://cube:4000/cubejs-api/v1` |
| Decision Layer API | 저장소의 Dockerfile로 빌드 | `8000` | `http://api:8000` |
| 웹 | `web/`에서 빌드 | `3000` | `http://web:3000` |

각각 별도 컨테이너이며 외부의 개인 인프라와 연결하지 않습니다. 데이터는 PostgreSQL에, 분석 실행 기록은 API의 별도 SQLite 볼륨에 저장합니다. Cube는 읽기 전용 DB 계정을 사용합니다. 이 Compose는 예시를 한 번에 띄우는 용도입니다. 기존 Cube를 사용하는 개발자는 [루트 README](../../README.ko.md)의 앱 실행 방법을 따르면 됩니다.

포트가 겹치면 다음과 같이 바꿉니다.

```bash
WEB_PORT=3013 API_PORT=8013 CUBE_PORT=4013 POSTGRES_PORT=5434 \
  docker compose up -d --build --wait
```

이 경우 웹은 `http://localhost:3013`, API는 `http://localhost:8013`, Cube API는 `http://localhost:4013/cubejs-api/v1`, DB는 `localhost:5434`입니다. 컨테이너 내부 주소는 바뀌지 않습니다. 계속 같은 포트를 쓰려면 이 폴더의 `.env.example`을 `.env`로 복사해 수정하세요. 이후에도 같은 포트가 적용됩니다. Compose 명령은 이 예제 폴더에서 실행하세요.

SQL 클라이언트로 접속할 때는 DB `chinook`, 사용자 `chinook_reader`, 비밀번호 `local-read-only`를 사용합니다. 모든 공개 포트는 localhost에만 연결되며 이 인증 설정은 로컬 개발용입니다.

## 분석해 보기

저장소 루트에서 MCP 어댑터를 설치하고 클라이언트 설정에서 실행 파일의 절대 경로와 `DL_API_URL=http://localhost:8000`을 지정합니다. 포트를 변경했다면 해당 API 포트를 쓰세요. Codex, Claude Code와 Claude Desktop 설정은 [MCP 가이드](../../docs/guides/mcp.md)에 있습니다.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
```

다음 질문으로 시작할 수 있습니다.

> 2023년 구매 항목 기준 판매액은 얼마이고, 어떤 장르가 가장 많이 기여했나요? 분석 단계와 근거도 보여 주세요.

기준값은 **전체 469.58, Rock 156.42**입니다. 데이터에 통화가 명시되어 있지 않아 달러 등으로 단정하지 않습니다. 웹의 **Runs**에서 질문, 지표와 분석 방법의 그래프, 단계별 결과와 쿼리를 확인합니다. 성공한 단계를 선택해 Recipe 초안으로 가져온 뒤 검토·저장할 수 있습니다.

처음에는 Recipe가 없습니다. 직접 만들거나 `templates/music-sales.yaml`을 로컬 `recipes/`에 복사하면 추이 → 장르별 분석 → 청구 국가별 분석의 예제를 실행할 수 있습니다.

청구서는 412건, 구매 항목은 2,240건입니다. 청구서 금액을 구매 항목과 조인한 뒤 그대로 합치면 중복됩니다. 판매 뷰는 구매 당시 단가 × 수량을 사용합니다. 비용 데이터가 없으므로 이익을 계산할 수 없고, 플레이리스트에 들어갔기 때문에 판매가 늘었다는 인과 주장도 할 수 없습니다. 플레이리스트와 연결 테이블은 DB에 적재하지만 판매 뷰에는 넣지 않았습니다.

작은 아티스트 그룹은 Method의 최소 건수 정책에 따라 순위에서 빠질 수 있습니다. 거래가 드문 예제라 마지막 구매일이 선택한 기간의 끝보다 앞서면 최신성 경고도 표시됩니다. 원본에는 데이터 적재 완료 시점이 없으므로 이 경고를 자동으로 무시하지 않습니다.

## 개발과 검증

11개 테이블 적재, 읽기 전용 계정, 독립 SQL 기준값을 확인합니다.

```bash
docker compose run --rm --no-deps import python verify.py
```

개발 의존성을 설치한 뒤 저장소 루트에서 실제 MCP → API → Cube → DB 경로를 테스트합니다.

```bash
DL_CHINOOK_API_URL=http://localhost:8000 \
  .venv/bin/pytest -q -s tests/provider/test_chinook_live.py
```

이 테스트는 등록된 Method를 명시적으로 호출합니다. AI의 방법 선택 능력을 평가한 결과는 아닙니다. [기준 질문](evals/cases.json)과 [AI 비교 평가 절차](../online-retail/evals/PROTOCOL.md)를 분리해서 사용하세요.

Python이나 웹 코드를 직접 수정하려면 데이터 서비스만 띄우고 [기여 안내](../../CONTRIBUTING.md)의 소스 실행 방법을 따릅니다. API용 Cube 환경변수는 [영문 개발 안내](README.md#develop-the-api-or-web-locally)에 있습니다.

```bash
docker compose up -d --build --wait postgres import cube
```

## 문제 확인과 종료

```bash
docker compose ps -a
docker compose logs --tail=100 import cube api
docker compose down
```

위 Compose 명령은 예제 폴더에서 실행합니다. 다운로드가 실패하면 `import` 로그를 확인하세요. 공식 JSON을 `data/ChinookData.json`에 직접 넣고 재시도할 수도 있으며, 이때도 체크섬을 확인합니다. `down`은 DB와 실행 기록을 보존합니다. `down -v`는 예제 DB·캐시·실행 기록 볼륨을 삭제합니다. 로컬 폴더의 Recipe 파일은 남습니다.
