---
title: 설치하고 시작하기
description: 샘플을 실행하고 AI를 연결합니다.
---

# 설치하고 시작하기

**Python 3.11 이상**과 **실행 중인 Docker**가 필요합니다. 빈 폴더에서 실행하세요.

## 1. 설치하고 실행하기

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install decision-layer
decision-layer demo
```

샘플 데이터를 준비하고 서버를 실행합니다. 첫 실행은 다운로드와 데이터 적재로 시간이 걸릴 수 있습니다.

## 2. 화면과 파일 확인하기

[관리자 화면](http://127.0.0.1:8000/ui/recipes)에서 준비된 분석을 살펴보고, [실행 기록](http://127.0.0.1:8000/ui/runs)에서 결과와 쿼리를 확인하세요.

작업 폴더에는 수정할 수 있는 Skill과 Python Method가 생성됩니다.

```text
작업 폴더/
├── decision-layer.yaml
├── recipes/
└── methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/method.py
    └── matching/method.py
```

- `SKILL.md`: AI가 따를 분석 지침
- `method.py`: 계산할 Python 함수
- `recipes/`: 저장한 분석 절차

파일을 수정하거나 추가하려면 [프로젝트에 등록하기](method-projects.md)를 보세요.

## 3. AI 연결하기

서버를 켜 두고 [MCP 연결 가이드](mcp.md)를 따라 연결하세요.

> 샘플의 2001년 2월 매출이 가장 큰 상품 부문을 찾고, 그 부문의 매장별 매출을 보여줘.

## 종료하고 다시 실행하기

`Ctrl+C`로 종료합니다. 데이터와 실행 기록은 유지됩니다.
같은 폴더에서 `decision-layer demo`를 실행하면 다시 시작합니다.

회사 데이터는 [Cube 연결](cube.md), 샘플의 출처와 구성은 [샘플 데이터 안내](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.ko.md)를 참고하세요.
