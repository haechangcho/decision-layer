---
title: 시작하기
description: 시맨틱 데이터에 분석 절차를 연결하고 재사용합니다.
---

# Decision Layer

Decision Layer는 시맨틱 레이어에 재사용할 수 있는 분석 절차를 연결합니다.
웹, Python, REST, MCP에서 실행하고 입력·쿼리·결과를 확인할 수 있습니다.

지표·차원·권한은 시맨틱 레이어가 정의합니다. Decision Layer는 그 데이터를 분석하는 절차를 관리합니다.

## 목적에 맞게 시작하기

| 목적 | 따라갈 문서 | 필요한 환경 |
| --- | --- | --- |
| 샘플 데이터로 제품 체험 | [샘플 실행](guides/quickstart.md) | Docker와 Compose |
| Method 작성·테스트 | [첫 Method 개발](guides/methods.md) | Python 3.11 이상 |
| 웹·API 개발 | [로컬 개발 환경](guides/development.md) | Python 3.11 이상, Node.js 22 |

## 세 가지 개념

- **Method**: 추세, 동료 집단 비교 같은 하나의 분석 기능입니다. 여러 쿼리를 조합할 수 있습니다.
- **Recipe**: 기존 Method와 시맨틱 참조로 구성한 팀의 분석 절차입니다.
- **Run**: 실행에 사용한 버전·입력·쿼리 근거·한계를 남긴 기록입니다.

기존 Method로 분석할 수 있으면 Recipe를 만듭니다. 새로운 계산이 필요하면 Method를 추가합니다.

## 내 데이터로 사용하기

[Cube](guides/cube.md) 또는 [dbt Semantic Layer](guides/dbt.md)를 연결한 뒤
[AI 클라이언트](guides/mcp.md)나 웹 앱에서 사용하세요.
[Recipe 만들기](guides/recipes.md)와 [실행 기록 읽기](guides/runs.md)에서 이어갈 수 있습니다.

구현 세부사항은 [아키텍처](ARCHITECTURE.md)와 [Method 계약](reference/method-contract.md)을 참고하세요.
