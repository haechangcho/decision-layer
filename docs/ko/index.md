---
title: 소개
description: 팀의 분석 방법을 등록하고 사람과 AI가 재사용합니다.
---

# Decision Layer

**팀이 검토한 분석 방법을 사람과 AI가 함께 사용합니다.**

Decision Layer는 semantic layer의 데이터와 등록된 분석 코드를 연결합니다. 반복하는 분석은 절차로 저장하고, 실행한 입력과 쿼리, 결과는 기록으로 남깁니다.

## 세 가지 개념

| 개념 | 역할 |
|---|---|
| **Method** | OLS나 추세 분석처럼 하나의 분석 방법 |
| **Recipe** | 여러 Method로 구성한 팀의 분석 절차 |
| **Run** | 한 번의 분석에서 사용한 입력, 쿼리와 결과 |

지표, 차원, 조인과 권한은 semantic layer가 정의합니다. Decision Layer는 그 데이터를 **어떻게 분석할지** 관리합니다.

## 원하는 곳에서 시작하세요

- **동작 원리 이해하기**: [Method 이해하기](guides/methods.md)에서 함수와 데이터가 연결되는 흐름을 봅니다.
- **코드로 살펴보기**: [Python 함수 연결 예제](tutorials/write-your-method)에서 순위 계산과 OLS의 입력과 결과를 읽습니다.
- **제품 사용하기**: [설치하고 시작하기](guides/quickstart.md)에서 샘플을 실행하거나 기존 Cube에 연결합니다.
- **팀의 분석 추가하기**: [프로젝트에 등록하기](guides/method-projects.md)에서 Method를 관리자 화면과 AI에 제공합니다.

분석 절차를 구성하려면 [Recipe 만들기](guides/recipes.md), 실행한 근거를 확인하려면 [실행 기록과 근거](guides/runs.md)를 보세요.
