# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [문서](docs/README.md) · [기여하기](CONTRIBUTING.md)

**팀의 분석 노하우를 반복해서 실행할 수 있게 만듭니다.**

Decision Layer는 semantic layer의 지표와 재사용 가능한 분석 절차를 연결합니다. 전문가는 등록된 분석 기능인 **Method**를 조합해 **Recipe**를 만들고, 사용자와 AI 도구는 Web이나 MCP로 실행합니다. 질문, 결과, 쿼리와 검증 내역은 **Run**에 남습니다.

![지표를 분석 절차로 연결하고 실행 근거를 기록하는 Decision Layer](docs/assets/decision-layer-overview.png)

## 시작하기

11개 테이블이 연결된 음악 상점 샘플로 시작하세요. Docker와 Compose만 있으면 됩니다. 별도의 데이터베이스, Cube 계정이나 로컬 토큰 설정은 필요하지 않습니다.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/chinook
docker compose up -d --build --wait
```

**http://localhost:3000/catalog** 에서 지표를 확인하세요. PostgreSQL, Cube, API와 Web이 함께 실행되고 연결도 설정됩니다. Recipe는 빈 상태로 시작합니다. 첫 실행에는 이미지 빌드와 고정된 버전의 샘플 데이터 다운로드가 필요합니다.

이미 Cube가 있다면 [기존 Cube 연결 가이드](docs/guides/cube.md)를 사용하세요. 포트 변경, 오프라인 실행, 데이터 출처와 종료 방법은 [샘플 가이드](examples/chinook/README.ko.md)에 있습니다.

## AI 도구 연결하기

샘플을 켜 둔 상태에서 **저장소 루트**로 이동하세요. MCP 어댑터 설치에는 Python 3.11 이상이 필요합니다.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
codex mcp add decision-layer --env DL_API_URL=http://localhost:8000 -- "$(pwd)/.venv/bin/decision-layer-mcp"
```

Claude 등 다른 클라이언트 설정은 [MCP 가이드](docs/guides/mcp.md)를 참고하세요. 어댑터는 stdio로 연결되며 Web과 같은 REST API를 사용합니다. Decision Layer 안에 LLM을 두지 않습니다.

연결한 AI 도구에 질문해 보세요.

> 2023년 구매된 트랙의 매출은 얼마이고, 어떤 장르의 매출이 가장 높았어? 분석 단계와 근거도 보여줘.

샘플의 기준값은 전체 **469.58**, 가장 높은 장르는 **Rock, 156.42**입니다. **http://localhost:3000/runs** 에서 질문, 지표 그래프와 결과를 확인하세요. 성공한 단계를 Recipe 초안으로 검토하고, 저장·게시하면 다시 사용할 수 있습니다. 이 기준값은 실행을 확인하기 위한 것이며 AI 정확도 향상을 입증하는 수치는 아닙니다.

## 구조

| 구분 | 역할 |
| --- | --- |
| **Semantic layer** | 지표, 차원, 조인, 데이터 단위와 접근 권한을 정의합니다. 현재는 Cube를 지원합니다. |
| **Method** | 입력·출력과 검증 조건이 정해진 하나의 분석 기능입니다. |
| **Recipe** | Method와 semantic 참조를 조합한 분석 절차입니다. 버전별 YAML로 저장합니다. |
| **Run** | 실행한 질문, 단계, 버전, 쿼리, 결과와 경고입니다. SQLite 또는 PostgreSQL에 저장합니다. |

Web, Python, REST와 MCP는 같은 명세와 실행 엔진을 사용합니다. AI 도구는 적절한 Recipe를 실행하거나 등록된 Method로 탐색합니다. 임의로 생성한 분석 코드를 실행하지 않습니다. Decision Layer는 BI 도구, semantic layer나 스케줄러가 아닙니다.

## 개발과 기여

- [로컬 개발](docs/guides/development.md): 수정 가능한 API·Web과 샘플 환경.
- [테스트](docs/guides/testing.md): 단위 테스트, 브라우저 테스트, 실제 MCP·Cube 연동 확인.
- [Method 추가](docs/guides/methods.md): 계약, 등록, 검증과 테스트.
- [기여하기](CONTRIBUTING.md): 이슈와 Pull Request 작성 방법.
- [아키텍처](docs/ARCHITECTURE.md)와 [설계 결정](docs/DECISIONS.md): 책임 경계와 실행 계약.

상세 개발 문서는 영어로 관리합니다.

## 현재 상태

초기 개발 단계입니다. Cube 연결, Recipe 그래프 편집, 미리보기, 초안·게시 버전과 Run에서 Recipe로 전환하는 기능을 제공합니다. 로그인, 작성 권한과 공동 승인함은 아직 구현되지 않았습니다. 기본 환경은 로컬용입니다. 공용 서비스로 공개하지 마세요. 샘플 인증 정보도 개발용입니다.

## 라이선스

[Apache License 2.0](LICENSE).
