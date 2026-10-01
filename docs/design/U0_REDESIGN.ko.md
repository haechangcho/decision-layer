# U0 v2: Microsoft Fabric / Fluent 2

기존 HTML 와이어프레임을 사용자 요청에 따라 대체한 U0 설계 기록이다. 검토 당시 화면은 `web` 앱의 `/design`에서 실행했다. 현재 `/design`은 제품 진입점 `/`으로 리다이렉트하며, 실제 Cube 카탈로그는 `/`, 연결 설정은 `/sources`에서 제공한다.

## 참고한 자료와 적용

| 공식 자료 | 확인한 원칙 | 이번 화면에 적용 |
|---|---|---|
| [Microsoft Fabric Home](https://learn.microsoft.com/en-us/fabric/fundamentals/fabric-home) | 작업 영역, 탐색, 검색, 최근 항목의 구조 | 고정된 왼쪽 탐색과 워크스페이스, 최근 분석 |
| [Fabric 실제 화면](https://learn.microsoft.com/en-us/fabric/fundamentals/media/fabric-home/tabs-object-explorer.png) | 화면 구획, 시각적 위계, 작업과 탐색의 분리 | 공식 스크린샷을 직접 확인. 제품의 복잡한 다중 탭 대신 단일 작업 유지 |
| [Fluent 2 Layout](https://fluent2.microsoft.design/layout) | 간격, 그룹, 반응형 배치 | 4px 기반 간격, 목록과 상세의 구획, 모바일에서 상세 패널 전환 |
| [Fluent 2 Navigation](https://fluent2.microsoft.design/components/web/react/core/nav/usage) | 짧은 이름과 예측 가능한 탐색 | 지표 탐색 / 내 분석 / 실행 기록. 연결은 보조 설정 위치 |
| [Fluent 2 Drawer](https://fluent2.microsoft.design/components/web/react/core/drawer/usage) | 맥락을 유지하는 짧은 보조 작업 | 분석 추가는 추천 선택 → 결과 확인 두 단계 |
| [Fluent 2 Dialog](https://fluent2.microsoft.design/components/web/react/core/dialog/usage) | 확인이 필요한 행동에만 모달 | 저장 변경 확인과 분석 기간 선택에만 모달 |
| [Fluent 2 Button](https://fluent2.microsoft.design/components/web/react/core/button/usage) | 주 행동을 명확히, 간결한 행동명 | 이 지표 분석하기 / 내 분석에 추가 / 분석 실행 |

브랜드 로고나 전체 화면을 복제하지 않는다. Microsoft Fabric의 작업 중심 구성을 참고하고, 공식 Fluent UI React 컴포넌트의 키보드·포커스·상태 표현을 사용한다.

## 핵심 변경

- A1~E 단계 버튼을 없애고 일상적인 탐색 메뉴로 바꿨다.
- 지표 선택과 추이·준비 상태 확인을 같은 화면에 둔다. 모바일은 선택한 지표만 패널에서 보여준다.
- Method 이름을 고르게 하지 않는다. 분석 후보를 선택하면 그룹별 비교 또는 추이로 이어진다.
- 기본 옵션은 숨기고 바로 미리보기를 보여준다. 변경할 때만 분석 옵션을 연다.
- 결과는 같은 분석 화면의 탭에서 확인한다. 결과 상세에서 하위 탐색을 추가할 수 있다.
- 데스크톱은 React Flow, 모바일은 읽기 쉬운 순서형 목록을 사용한다.
- 빈 검색, 연결 실패, 환경변수 고정, 읽기 전용, 진행 상태, 되돌리기, 저장 완료를 실제로 조작할 수 있다.
- 데이터 시각화는 Recharts, 도구 아이콘은 Lucide를 사용한다.

## 실행과 검증

역사적 U0 시안은 아래 디자인 기준을 기록하기 위한 것이다. 현재 웹 경로는 `/`(실제 시맨틱 카탈로그), `/sources`(Cube 설정), `/methods`, `/recipes`, `/runs`다. `/design`은 기존 공유 URL 호환을 위한 루트 리다이렉트다.

`npm run build`로 타입 검사와 프로덕션 빌드를 수행한다. 별도로 실행 중인 서버를 대상으로 `npm run test:design`을 실행한다. 기본 주소는 `http://127.0.0.1:5210`; 변경 시 `PLAYWRIGHT_BASE_URL`을 지정한다. Chromium 설치는 `npx playwright install chromium`. 기존 Chromium을 쓸 경우 `PW_CHROMIUM_EXECUTABLE`을 지정한다.

Playwright 시나리오는 데스크톱 1440px와 모바일 390px에서 검색·필터, 지표 선택, 미리보기, 저장·되돌리기, 실행·하위 탐색, 연결 관리자 확인·오류·고정 필드·준비 점검, MCP 기록 추가, 읽기 전용, 키보드 닫기 및 가로 넘침을 확인한다.

## 경계

이 문서는 U0 당시의 검토 범위와 한계를 기록한다. 이후 실제 Cube 카탈로그 탐색, 연결 화면, Recipe 편집 그래프가 제품 경로에 구현됐다. 그래프는 Recipe의 Method 단계와 설정을 편집한다. API secret 저장 시 `DL_SOURCE_CONFIG_KEY`가 필요하고, 소스 편집은 `DL_SOURCE_ADMIN_TOKEN`, Recipe 저장은 `DL_RECIPE_ADMIN_TOKEN`으로 각각 보호한다.

Graph는 U0 시각 검토 범위다. ADR-011의 변경이나 U3 실행 명세 결정이 완료되었다는 의미는 아니다.
