---
title: 빠른 시작
description: 분석을 저장하고 다른 기간에 같은 절차를 실행합니다.
---

# 빠른 시작

Git과 실행 중인 Docker Compose v2가 필요합니다. 회사 계정이나 모델 API 키 없이
작은 합성 데이터로 실제 Cube와 실행 엔진을 체험합니다.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
bash scripts/demo.sh
```

[실행 기록](http://localhost:3100/runs)을 여세요. 스크립트가 분석·Recipe 저장·재실행을
수행하고 각 Run 링크를 출력합니다. 첫 빌드는 이미지·패키지를 다운로드하므로 몇 분 이상 걸릴 수 있습니다.

1. 1월: Home 매출 6,200 → 해당 부문의 지역 조사.
2. 저장: 실행한 분석을 Recipe로 등록.
3. 2월: 같은 Recipe가 Grocery 매출 6,720을 선택.
4. 3월: 두 부문이 동률이므로 지역 조회 전에 추가 입력 요청.

각 Run에서 사용한 규칙과 실제 선택, 쿼리, 경고를 확인하세요. 합성 데이터의 기술적 순위이며
인과관계를 입증하지 않습니다. 스크립트 데모는 LLM 성능 평가가 아닙니다.

## AI로 재사용

[MCP 연결](./mcp.md)의 로컬 어댑터를 설치하고 API를 `http://localhost:8100`,
Web 주소를 `http://localhost:3100`으로 설정하세요.

> 저장된 부문 분석 절차를 2026년 2월에 재사용해줘. 매출 1위 부문을 찾고 그 부문의 지역별 매출과 근거를 보여줘.

모델은 기존 AI 클라이언트가 제공합니다.

```bash
bash scripts/demo.sh replay
bash scripts/demo.sh stop
```

[포트 변경·초기화·샘플 설명](https://github.com/haechangcho/decision-layer/blob/main/examples/quickstart/README.ko.md)
· [더 큰 Complete Journey 예제](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)

## 다음 단계

[Cube 연결](./cube.md) · [dbt 연결](./dbt.md) · [Recipe 만들기](./recipes.md) · [Method 기여](./methods.md)
