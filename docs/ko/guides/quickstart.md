---
title: 설치하고 시작하기
description: 설치하고 샘플을 실행한 뒤 AI를 연결합니다.
---

# 설치하고 시작하기

**Python 3.11 이상**과 **실행 중인 Docker**를 준비하세요. 빈 작업 폴더에서 시작합니다.

## 1. 설치하고 실행하기

아래 명령을 순서대로 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade --pre 'decision-layer[stats,mcp]'
decision-layer demo
```

관리자 화면과 분석 라이브러리를 설치하고, 샘플 데이터를 준비해 서버를 실행합니다.
첫 실행에는 다운로드 시간이 걸릴 수 있습니다.

## 2. 화면과 파일 확인하기

[관리자 화면](http://127.0.0.1:8000/ui/recipes)을 열어 준비된 매출 분석을 살펴보세요.
[실행 기록](http://127.0.0.1:8000/ui/runs)에서 조회한 데이터와 결과를 확인할 수 있습니다.

작업 폴더에는 직접 수정할 Skill과 Python Method가 생성됩니다.

```text
작업 폴더/
├── decision-layer.yaml
└── sample_shop/methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/method.py
    └── matching/method.py
```

`SKILL.md`는 AI가 따를 분석 지침이고, `method.py`는 계산할 Python 코드입니다.
수정하거나 추가하는 방법은 [Method 프로젝트](./method-projects.md)에서 확인하세요.

## 3. AI 연결하기

서버를 켜 둔 상태에서 [MCP 연결 가이드](./mcp.md)를 따라 AI 클라이언트에 연결하세요.
그다음 아래처럼 질문할 수 있습니다.

> 2026년 2월 매출 1위 부문을 찾고, 지역별 매출을 설명해줘.

## 종료하고 다시 실행하기

터미널에서 `Ctrl+C`를 누르면 종료됩니다. 코드, 데이터와 실행 기록은 유지됩니다.
같은 프로젝트 폴더에서 `decision-layer demo`를 실행하면 다시 시작합니다.

회사 데이터로 분석하려면 [Cube 연결 가이드](./cube.md)를 확인하세요.
