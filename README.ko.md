# HEARTCOUNT Decision Layer

**우리 팀의 분석 노하우를 AI가 실행할 수 있는 절차로.**

Decision Layer는 Semantic Layer 위에서 **어떤 지표를 함께 보고, 어떤 순서와 방법으로 분석할지** 관리하는 오픈소스 프레임워크입니다. 조직의 분석 절차를 저장하고, 사람과 AI Agent가 새로운 데이터에 다시 적용할 수 있게 합니다. 실행한 단계와 사용한 데이터, 쿼리, 검증 결과는 함께 기록됩니다.

[문서](https://decision-layer-docs.vercel.app/ko/) · [빠른 시작](#5-decision-layer-실행하기) · [활용 예시](#6-어떻게-활용하나요) · [English](README.en.md) · [도입 문의](mailto:support@idk2.co.kr)

## 1. 이게 뭔가요?

“이번 달 매출이 왜 줄었나요?”라는 질문에 숙련된 분석가는 숫자 하나만 조회하지 않습니다. 비교 기간을 정하고, 상품군·지역·고객군을 좁혀 가며, 판매 수량과 단가·할인율을 함께 확인합니다.

Decision Layer는 이러한 **절차 지식**(procedural knowledge)을 실행 가능한 Recipe로 관리합니다. 검토한 분석을 Recipe로 저장하면, 다음 달에도 같은 절차를 사용하면서 조사 대상은 새 데이터에 따라 다시 선택할 수 있습니다.

> 절차는 재사용하고, 답은 현재 데이터로 다시 계산합니다.

## 2. 왜 필요한가요? 무엇이 다른가요?

### Semantic Layer가 있어도 분석 절차는 필요합니다

Semantic Layer는 매출의 정의, 집계 방식, 상품·고객·지역의 관계를 관리합니다. AI는 이를 통해 일관된 지표를 조회할 수 있습니다. 하지만 지표의 정의만으로는 다음 질문까지 정해지지 않습니다.

- 매출과 함께 판매 수량, 주문 수, 단가 중 무엇을 확인할 것인가?
- 상품군·지역·고객군 중 어떤 차원부터 살펴볼 것인가?
- 매출 규모가 큰 집단과 감소액이 큰 집단 중 어디를 먼저 조사할 것인가?
- 조사 대상이 동률이거나 필요한 입력이 빠졌을 때 어떻게 할 것인가?

이 절차가 매번 AI의 판단에만 맡겨지면, 같은 질문에도 비교 기준과 분석 경로가 달라질 수 있습니다. Decision Layer는 팀이 합의한 절차를 명시하고, 실제 실행이 그 절차를 따랐는지 확인할 수 있게 합니다.

| 구분 | Semantic Layer | Decision Layer |
| --- | --- | --- |
| 핵심 질문 | 이 지표는 무엇이며 어떻게 계산하는가? | 이 질문을 어떤 순서와 방법으로 분석하는가? |
| 관리 대상 | 지표 정의, 차원, 조인, 집계 단위, 접근 권한 | 관련 지표, 분석 차원, Method, 단계 연결, 선택 규칙 |
| 매출 분석 예 | 완료된 주문의 할인 후 금액을 매출로 집계 | 전월과 비교하고, 감소액이 큰 상품군 → 지역 → 고객군을 조사 |

두 계층을 함께 사용하면 **지표의 의미와 분석 절차를 각각 관리**할 수 있습니다. 지표 계산식과 조인·권한은 Semantic Layer에 두고, Decision Layer는 그 정의를 참조합니다.

### SKILL.md와는 무엇이 다른가요?

SKILL.md로도 분석 지침을 전달하고, 스크립트나 도구를 묶을 수 있습니다. Decision Layer는 지침을 실행할 때 필요한 입력·단계 연결·검증·기록을 공통 실행 엔진에서 관리합니다.

| 구분 | SKILL.md 중심의 구성 | Decision Layer |
| --- | --- | --- |
| 절차 표현 | 자연어 지침과 연결된 코드·도구 | Method와 지표 참조로 구성한 Recipe |
| 입력과 단계 연결 | 사용하는 도구·스크립트에서 구현 | 입력 타입과 이전 단계의 선택 결과를 계약으로 관리 |
| 실행과 근거 | 구성에 따라 별도로 구현 | Run에 적용 입력, Method·Recipe 버전, 쿼리와 경고를 기록 |
| 여러 인터페이스에서 사용 | 클라이언트와 연결 방식에 따라 구성 | Web·Python·REST·MCP가 같은 실행 모델 사용 |

둘은 함께 사용할 수 있습니다. Skill은 “언제 이 분석을 사용할지”를 안내하고, Decision Layer는 해당 Recipe를 실행하는 도구가 될 수 있습니다. 같은 절차를 적용한다는 것은 분석 경로와 기준을 관리한다는 뜻이며, AI의 설명 문장이나 분석적 정답을 보장한다는 뜻은 아닙니다.

## 3. 누구를 위한 도구인가요?

**정형 데이터를 분석하는 AI Agent를 만들고 싶은 개발자와 조직**을 위한 도구입니다.

- **Agent·App 개발자:** 지표 조회에 더해 재사용 가능한 분석 기능과 절차를 연결하고 싶을 때.
- **데이터 분석가·현업 전문가:** 반복하는 분석 노하우를 팀과 AI가 함께 사용할 수 있게 만들고 싶을 때.
- **데이터 플랫폼 팀:** 기존 Semantic Layer를 활용하면서 분석 실행과 근거를 확인할 수 있게 하고 싶을 때.

매출뿐 아니라 비용, 고객 이탈, 운영 품질 등 반복해서 조사하는 업무 질문에 적용할 수 있습니다. 업무별 지표와 적절한 분석 절차를 먼저 정의해야 합니다.

## 4. 어떻게 구성되어 있나요?

![App과 AI Agent가 MCP 또는 API로 Decision Layer를 호출하고, Semantic Layer를 통해 DB와 Mart의 데이터를 조회하는 구조](docs/assets/readme-architecture.svg)

| 구성 요소 | 역할 |
| --- | --- |
| **Semantic Source** | Cube 또는 dbt Semantic Layer의 지표·차원과 연결 |
| **Method** | 집계, 기간 비교, 드릴다운 등 하나의 분석 기능 |
| **Recipe** | Method와 지표를 묶은 조직의 재사용 가능한 분석 절차 |
| **Run** | 한 번의 분석 실행과 단계별 결과·근거 기록 |
| **공통 실행 엔진** | 입력·범위 검증, 단계 실행, 대상 선택, 실행 근거 관리 |
| **Web · Python · REST · MCP** | 사람이 검토하거나 App·AI Agent에서 분석을 호출하는 인터페이스 |

현재 Semantic Source로 **Cube REST API**와 **공식 dbt Semantic Layer GraphQL API**를 지원합니다. 기본 조회 Method는 집계, 추이·기간 비교, 드릴다운입니다. 새로운 Method는 Python으로 추가할 수 있습니다.

AI는 등록된 Method와 Recipe를 선택하고 결과를 설명합니다. 분석 실행은 공통 엔진을 거치며, AI가 즉석에서 생성한 분석용 Python·SQL을 실행하는 방식은 사용하지 않습니다.

[아키텍처 자세히 보기](docs/ko/ARCHITECTURE.md) · [Method 개발 가이드](docs/ko/guides/methods.md) · [Recipe 가이드](docs/ko/guides/recipes.md)

## 5. Decision Layer 실행하기

### 샘플 데이터로 먼저 체험하기

**Git과 실행 중인 Docker Compose v2**를 준비한 뒤 실행하세요.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
bash scripts/demo.sh
```

PostgreSQL·Cube·Decision Layer API·Web과 작은 합성 상점 샘플을 준비합니다. 이 스크립트 데모에는 회사 데이터나 모델 API 키, 로컬 Python 설치가 필요 없습니다. 첫 실행은 이미지와 패키지를 내려받으므로 몇 분 이상 걸릴 수 있습니다.

실행 후 [Web에서 분석 기록 보기](http://localhost:3100/runs)를 여세요.

| 기본 샘플 | 확인할 동작 |
| --- | --- |
| 1월 | 매출 1위 Home을 선택하고 지역별 매출 조사 |
| 2월 | 같은 Recipe가 새 1위 Grocery를 선택하고 지역별 매출 조사 |
| 3월 | 두 부문이 동률이면 지역 조회 전에 추가 입력 요청 |

```bash
# 새 실행 기록을 만들며 샘플 다시 실행
bash scripts/demo.sh replay

# 데이터는 보존하고 서비스 종료
bash scripts/demo.sh stop
```

### Claude Code에서 질문하기

Node.js와 Claude Code도 준비되어 있다면, 복제한 저장소에서 다음 명령으로 샘플 준비와 MCP 등록을 진행할 수 있습니다.

```bash
node scripts/install.mjs setup --client claude
```

Claude Code를 다시 시작한 뒤 질문하세요. 모델 연결은 AI 클라이언트에서 별도로 준비합니다.

> 저장된 부문 분석 절차를 2026년 2월에 재사용해줘. 매출 1위 부문을 찾고 그 부문의 지역별 매출을 확인해줘. 근거와 한계도 설명해줘.

[설정·종료·제약 사항](examples/quickstart/README.ko.md) · [Codex 등 MCP 클라이언트 연결](docs/ko/guides/mcp.md)

## 6. 어떻게 활용하나요?

### ① 회사의 Semantic Layer 연결하기

DB·Mart의 지표와 차원을 Semantic Layer에 정의한 뒤, Decision Layer에 소스를 연결합니다. 예를 들어 매출 분석에는 매출, 판매 수량, 주문 수, 실판매단가, 할인율과 상품군·지역·고객군을 준비할 수 있습니다.

이미 운영하는 Cube나 dbt Semantic Layer가 있다면 기존 정의를 활용하세요. Semantic Layer 구축이나 기존 SQL·Mart의 모델링에 도움이 필요하면 [support@idk2.co.kr](mailto:support@idk2.co.kr)로 문의해 주세요.

[Cube 연결 가이드](docs/ko/guides/cube.md) · [dbt 연결 가이드](docs/ko/guides/dbt.md)

### ② 우리 팀의 분석 절차를 Recipe로 구성하기

기존 Method를 조합해 Recipe를 만들거나, 유용했던 Run을 검토한 뒤 Recipe로 저장합니다. Web에서 구성하고 YAML로 세부 설정을 관리할 수 있습니다. AI 코딩 도구로 Recipe와 Python Method 초안을 작성하는 것도 가능합니다. 업무 기준에 맞는지 검토한 뒤 등록해 사용하세요.

다음은 **6개월치 합성 소매 데이터**로 구성하고 로컬 PostgreSQL·Cube에서 실행한 매출 변화 분석 예시입니다. 위의 설치용 기본 샘플과는 별도의 데이터·Recipe를 사용합니다.

> 이번 달 매출은 전월과 비교해 어디서 줄었나요? 상품군 → 지역 → 고객군 순서로 좁혀 보고, 판매 수량·실판매단가·할인율을 함께 확인해 주세요.

Recipe에는 다음 절차를 저장합니다.

1. 이번 달과 전월의 전체 매출 및 관련 지표를 비교합니다.
2. 매출 감소액이 가장 큰 상품군을 찾습니다.
3. 선택한 상품군 안에서 감소액이 가장 큰 지역을 찾습니다.
4. 그 지역 안에서 감소액이 가장 큰 고객군을 찾습니다.
5. 최종 집단의 수량·단가·할인율을 비교합니다. 선택 대상이 동률이면 추가 입력을 요청합니다.

| 같은 Recipe를 적용한 기간 | 조사 대상 | 확인한 내용 |
| --- | --- | --- |
| 3월 vs. 2월 | 가전 → 수도권 → 기업 고객 | 매출 3,240만 → 1,620만 원. 수량 240 → 120개, 단가 동일 |
| 4월 vs. 3월 | 패션 → 영남권 → 프리미엄 고객 | 매출 648만 → 504만 원. 수량 동일, 할인율 10% → 30% |
| 5월 vs. 4월 | 생활용품·식품의 감소액 동률 | 각각 162만 원 감소. 조사할 상품군을 묻고 지역 조회는 대기 |

**저장하는 것은 특정 상품군의 이름이 아니라, 매번 현재 데이터에서 조사 대상을 선택하는 규칙입니다.**

![4월 매출 변화 분석 결과. 패션·영남권·프리미엄 고객의 매출과 수량·단가·할인율을 함께 확인하는 실제 Web 화면](docs/assets/revenue-change-april.jpg)

<details>
<summary>5월: 동률이면 어떻게 되나요?</summary>

생활용품과 식품의 감소액이 같아 조사할 상품군을 선택하도록 요청합니다. 입력을 기다리는 동안 지역·고객군 조회는 실행하지 않습니다.

![생활용품과 식품 중 조사 대상을 요청하고, 대기 중인 지역 단계의 쿼리가 0개임을 보여주는 실제 화면](docs/assets/revenue-change-may.jpg)

</details>

이 예시는 분석 절차의 재사용을 보여주기 위해 설계한 합성 데이터입니다. 수량·단가 등의 변화는 관측 결과이며, 변화가 발생한 업무 원인까지 입증한 것은 아닙니다.

### ③ MCP 또는 API로 App·Agent에 연결하기

등록한 지표와 Recipe를 App에서 사용하려면 REST API 또는 Python 인터페이스를, AI 클라이언트에서 사용하려면 제공되는 MCP 어댑터를 연결합니다. Web과 같은 분석 실행 모델을 사용하므로 결과와 근거를 함께 확인할 수 있습니다.

이 저장소의 MCP 어댑터는 **로컬 stdio 방식**이며 Claude Code·Codex 등의 연결 설정을 제공합니다. HEARTCOUNT Semantic MCP와의 연계나 조직 환경에 맞는 App 연결은 별도로 구성합니다.

[MCP 연결 안내](docs/ko/guides/mcp.md)

### ④ 직접 App을 개발하기 어렵다면

HEARTCOUNT의 **Semantic MCP와 전용 Decision Agent를 활용하는 도입 방식**도 상담할 수 있습니다. 기관·조직의 데이터 연결, Semantic Layer 모델링, 업무별 Recipe 구성과 Agent 연계에 도움이 필요하면 [support@idk2.co.kr](mailto:support@idk2.co.kr)로 연락해 주세요.

아래는 **Claude와 HEARTCOUNT Semantic MCP를 연결한 제조 분석 데모**입니다. 연결 화면과 KPI 확인·분석 흐름을 영상으로 볼 수 있습니다.

[![Claude에서 HC Semantic MCP를 활성화한 실제 데모 화면 — 클릭하면 소개 글과 영상을 볼 수 있습니다](docs/assets/heartcount-semantic-mcp-claude.jpg)](https://community.heartcount.io/ko/manufacturing-decision-intelligence-bga/)

[활용 사례와 영상 보기](https://community.heartcount.io/ko/manufacturing-decision-intelligence-bga/)

이 영상은 HEARTCOUNT의 별도 활용 사례이며, 이 저장소의 설치용 샘플 실행 영상과는 다릅니다.

## 7. 어떻게 발전할 계획인가요?

다음은 **향후 확장 방향**입니다. 현재 설치만으로 제공되는 기능과 구분합니다.

- **Always-on Analytical Agent:** 지표와 데이터의 의미 있는 변화를 감지하고, 적합한 Recipe로 조사한 뒤 근거가 포함된 보고서를 작성하는 흐름을 발전시킬 계획입니다. 반복 알림을 줄이고, 사람이 검토할 변화에 집중하는 방향을 지향합니다.
- **산업·업무별 Recipe와 Method 확대:** 매출·고객·비용·운영 등 반복 질문에 사용할 수 있는 예제와 분석 기능을 보강할 계획입니다.

적용하고 싶은 업무나 필요한 분석 기능은 [GitHub Issues](https://github.com/haechangcho/decision-layer/issues)에서 제안해 주세요.

## 함께 읽으면 좋은 글

- [SQL 자산을 활용한 규칙 기반 시멘틱 모델링](https://community.heartcount.io/ko/sql-to-semantic-layer-2/) — 기존 SQL을 Semantic Layer 모델로 연결하는 HEARTCOUNT의 접근을 소개합니다.
- [믿어도 되나요 AI의 숫자를](https://community.heartcount.io/ko/semantic-mcp-decision-agent/) — AI의 답변을 지표 정의·업무 규칙·권한·근거와 연결해야 하는 이유를 설명합니다.

## 개발과 기여

분석 Method, 업무별 Recipe, 재현 가능한 예제, 문서 개선에 기여할 수 있습니다. Method 개발은 Python 3.11 이상에서 시작할 수 있습니다.

[작은 기여 과제](docs/guides/contribute-examples.md) · [Method 개발](docs/ko/guides/methods.md) · [개발 환경](docs/ko/guides/development.md) · [기여 안내](CONTRIBUTING.md)

분석의 타당성은 지표 정의, 데이터 품질, 선택한 절차와 방법의 가정에 달려 있습니다. 현재의 평가 범위와 성능 실험은 [평가 안내](docs/ko/guides/evaluation.md)와 [파일럿 결과](docs/guides/benchmark-pilot.md)에서 확인할 수 있습니다.

## 도입 문의 · 라이선스

**기관·조직에 직접 도입하고 싶거나, Semantic Layer·Recipe·Agent 구성에 도움이 필요하신가요?**

[support@idk2.co.kr](mailto:support@idk2.co.kr)로 사용 목적과 현재 데이터 환경을 알려 주세요.

오픈소스 라이선스: [Apache 2.0](LICENSE)
