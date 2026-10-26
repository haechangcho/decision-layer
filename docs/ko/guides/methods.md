# Method 이해하기

Method는 재사용할 분석 방법입니다. **Python Method**는 계산 함수를 실행하고, **Skill Method**는 AI가 따를 분석 절차를 담습니다.

## 기본 Method

- **지표 조회**: 선택한 지표와 기간의 값을 조회하는 Skill
- **그룹별 분석**: 지표를 나누고 선택한 그룹을 살펴보는 Skill
- **OLS 회귀분석**: 다른 변수를 고려해 변수 간 관계를 계산하는 Python 함수
- **매칭 분석**: 조건이 비슷한 두 집단을 비교하는 Python 함수

Python Method는 관리자 화면에서 테스트하고, Skill은 MCP에 연결한 AI로 실행합니다.

## 등록할 때와 실행할 때

- **등록**: 계산 함수와 필요한 데이터 조건을 정합니다.
- **실행**: 실제 지표, 차원과 기간을 선택합니다.

예를 들어 OLS 함수를 한 번 등록하면, 고객별 구매 금액과 광고 노출 횟수를 연결해 분석할 수 있습니다.
지표 정의와 집계 방식은 semantic layer에서 관리합니다.

## 실행 흐름

**Method 선택 → 데이터 연결 → 조회와 계산 → 결과 기록**

AI는 Method의 입력 조건과 semantic catalog를 보고 데이터를 선택합니다. 의미나 기간이 모호하면 사용자에게 확인합니다.
Decision Layer는 선택한 데이터를 조회해 함수를 실행하고 입력, 쿼리와 결과를 Run에 남깁니다.

[Python Method 만들기](../tutorials/write-your-method)에서 코드와 결과를 살펴보고, [프로젝트에 등록하기](method-projects.md)로 이어가세요.
등록 옵션은 [Method API](../reference/method-contract.md)에 있습니다.
