---
title: 빠른 시작
description: 샘플을 실행하고 지표와 분석 기록을 확인합니다.
---

# 빠른 시작

로컬 Cube 예제의 소매점 데이터로 지표 확인부터 분석 기록까지 경험할 수 있으며 Recipe는 비어 있는 상태로 시작합니다.

Method 기여자는 이 샘플 없이 [Python 전용 가이드](./methods.md)로 시작할 수 있습니다.

## 1. 예제 실행

Docker와 Compose가 필요합니다. 터미널에서 실행하세요.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
```

```bash
docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900
```

웹은 localhost:3000, API는 localhost:8000, Cube는 localhost:4000입니다. 첫 실행은 데이터를 내려받아 적재하므로 몇 분 걸릴 수 있습니다. 처음에는 실행 기록과 Recipe가 비어 있고, 다시 실행하면 기록이 유지됩니다.

회사의 dbt 환경은 [공식 Semantic Layer API](./dbt.md)로 연결합니다. dbt 공식 API는 로컬 Docker 예제로 제공하지 않습니다. 종료 방법은 [샘플 안내](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)를 확인하세요.

## 2. 지표 확인

[로컬 웹 앱](http://localhost:3000)을 열고 **Metrics**에서 **Retailer receipts**를 선택하세요. 지표 정의와 사용할 수 있는 차원을 확인할 수 있습니다. 지표의 의미는 선택한 시맨틱 레이어가 관리하고 Decision Layer는 카탈로그에서 읽습니다.

## 3. MCP로 분석

[Claude 또는 Codex](./mcp.md)에 로컬 MCP 어댑터를 연결한 뒤 질문하세요.

> 전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 분석 단계와 근거도 보여줘.

웹의 **Runs**에서 질문, 각 단계에 사용한 Method, 결과와 쿼리를 확인하세요. 분석이 완료되면 **Recipe로 등록**을 눌러 같은 절차와 설정을 다시 쓸 수 있습니다.

## 다음 단계

- [기존 Cube 연결](./cube.md): 조직의 지표로 분석하기
- [dbt Semantic Layer 연결](./dbt.md): 조직의 공식 API로 분석하기
- [Recipe 만들기](./recipes.md): 반복하는 질문을 절차로 저장하기
- [실행 기록 읽기](./runs.md): 결과와 근거 검토하기
- [Method 기여하기](./methods.md): 새로운 분석 기능 추가하기

::: info 예제 데이터
원본의 상대적인 일자를 예제용 달력 날짜로 변환했습니다. 실제 구매 연도가 아니며 인과 효과가 확인된 데이터도 아닙니다. 결과를 해석하기 전에 [샘플 안내](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)를 확인하세요.
:::
