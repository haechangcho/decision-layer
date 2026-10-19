# 절차를 저장하고, 답은 다시 계산합니다

1월에는 Home, 2월에는 Grocery가 매출 1위이고 3월에는 동률인 작은 합성 상점 데이터입니다.
같은 Recipe가 새로운 선두 부문을 선택하고, 동률에서는 추가 입력을 요구하는지 확인합니다.


## Claude Code 또는 Codex에 설치

복제한 저장소에서 Node.js, 사용할 AI 클라이언트, Docker가 준비된 상태로 실행하세요.

```bash
node scripts/install.mjs setup --client claude
# Codex를 선택하면:
node scripts/install.mjs setup --client codex
```

런타임을 `~/.local/share/decision-layer/runtime`에 준비하고 샘플을 검증한 뒤
`decision-layer-demo`를 등록합니다. 선택한 클라이언트를 다시 시작하고 아래 질문을 하세요.
Python 설치나 MCP JSON 편집은 필요 없습니다. Docker가 켜져 있으면 중지된 API도
다시 시작합니다. 같은 이름의 다른 연결은 덮어쓰지 않습니다. 웹은 근거 확인용입니다.

`node scripts/install.mjs doctor`로 상태를 확인하고 `node scripts/install.mjs stop`으로 종료합니다.
연결 제거는 `claude mcp remove decision-layer-demo`입니다.
macOS/Linux 셸과 Windows WSL2를 대상으로 하며 네이티브 Windows 설치는 검증하지 않았습니다.

## 실행

Git과 실행 중인 Docker Compose v2가 필요합니다. 이 스크립트 데모에는 회사 계정,
로컬 Python, 모델 API 키가 필요 없습니다. 첫 빌드는 인터넷에서 이미지와 패키지를 받아
몇 분 이상 걸릴 수 있습니다.

저장소 루트에서:

```bash
bash scripts/demo.sh
```

http://localhost:3100/runs 를 여세요. 터미널에 실행별 링크도 표시됩니다.
API는 8100 포트입니다. 기존 Complete Journey와 다른 프로젝트·포트를 사용합니다.
포트가 사용 중이면 `DL_DEMO_WEB_PORT=3200 DL_DEMO_API_PORT=8200 bash scripts/demo.sh`로 실행하세요.

## 확인할 결과

| 기간 | 매출 선두 부문 | 매출 | 해당 부문의 North 매출 |
| --- | --- | ---: | ---: |
| 2026년 1월 | Home | 6,200 | 3,720 |
| 2026년 2월 | Grocery | 6,720 | 4,032 |
| 2026년 3월 | 두 부문 동률 | 각각 3,720 | 자동 선택하지 않음 |

실제 Cube와 공통 REST 실행 엔진을 사용합니다. 1월 분석을 Recipe로 저장한 뒤
2월에 재실행하며, 1월의 부문 이름이나 날짜를 그대로 복사하지 않습니다.
3월은 지역 조회 전에 입력을 요구합니다. 각 Run에서 규칙·선택된 값·쿼리·경고를 확인하세요.

360개 행은 이 저장소를 위해 작성한 합성 데이터이며 Apache-2.0으로 배포합니다.
지표 정의는 Cube 모델에 있습니다. 매출의 표본 수가 공급자에서 선언되지 않아 최소 표본 수
검사가 적용되지 않는다는 경고를 유지합니다. 순위 분석이며 변화의 인과관계를 입증하지 않습니다.

## AI에서 사용하기

스크립트 자체는 LLM을 쓰지 않습니다. [MCP 안내](../../docs/ko/guides/mcp.md)를 따라
어댑터를 설치하고 `DL_API_URL=http://localhost:8100`,
`DL_WEB_URL=http://localhost:3100`을 지정하세요. 클라이언트별 설정 형식은 다를 수 있으며
복사할 stdio 설정은 [영문 안내](README.md#ask-your-ai)에 있습니다.

> Decision Layer에 저장된 부문 분석 절차를 2026년 2월에 재사용해줘.
> 매출 1위 부문을 찾고 그 부문의 지역별 매출을 확인해줘. 근거와 한계도 설명해줘.

이후 3월에 재실행해 달라고 요청하세요. AI 클라이언트의 모델 연결은 별도로 필요합니다.

## 다시 실행·종료

```bash
bash scripts/demo.sh replay
bash scripts/demo.sh stop
```

재실행은 새 Run과 Recipe를 만듭니다. 종료는 데이터를 보존합니다.
공용 로컬 서비스 계정을 사용하므로 사용자 간 권한 분리를 검증한 데모는 아닙니다.
초기화와 전체 실행 근거 추출은 [영문 안내](README.md#replay-evidence-and-shutdown)를 참고하세요.

Codex 상태 확인: `node scripts/install.mjs doctor --client codex`. 연결 제거: `codex mcp remove decision-layer-demo`.
절차 저장은 초안을 만들고, 검토 후 게시해야 새 기간에 실행할 수 있습니다. 예제 replay는 두 단계를 모두 수행합니다.
