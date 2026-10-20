---
title: 설치하고 시작하기
description: PyPI로 설치하고 샘플 데이터 또는 내 Cube에 연결합니다.
---

# 설치하고 시작하기

Python 3.11 이상에서 설치합니다. 관리자 화면도 패키지에 포함되어 있습니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --pre 'decision-layer[stats,mcp]'
```

현재는 사전 배포 버전이므로 `--pre`를 사용합니다. `stats`는 데이터 처리와 통계 계산, `mcp`는 AI 연결에 필요한 패키지를 함께 설치합니다.

## 샘플로 먼저 체험하기

실행 중인 Docker와 Compose v2를 준비한 뒤 실행합니다.

```bash
decision-layer demo
```

명령이 PostgreSQL과 Cube를 Docker로 준비하고, 설치된 패키지로 관리자 화면과 API를 실행합니다.
회사 데이터나 AI 연결은 필요하지 않습니다. 첫 실행에는 Docker 이미지 다운로드 시간이 걸립니다.

[관리자 화면](http://127.0.0.1:8000/ui/recipes)을 여세요. 준비된 분석은 다음 과정을 보여줍니다.

1. 1월 매출 1위 Home의 지역별 매출을 확인합니다.
2. 이 분석 절차를 Recipe로 저장합니다.
3. 2월에는 같은 Recipe가 새 매출 1위 Grocery를 선택합니다.
4. 3월에는 공동 1위가 있어 사용자에게 선택을 요청합니다.

[실행 기록](http://127.0.0.1:8000/ui/runs)에서 입력, 쿼리와 결과를 확인하세요.
합성 데이터로 등록된 분석 절차를 실행하는 예제이며, AI가 답을 생성하는 데모는 아닙니다.

### 종료와 보관 위치

실행한 터미널에서 `Ctrl+C`를 누르면 서버와 샘플 컨테이너가 종료됩니다.
데이터, Recipe와 실행 기록은 유지되며, 다시 `decision-layer demo`로 시작할 수 있습니다.

기본 프로젝트는 `~/.decision-layer/demo/`에 있습니다.
샘플 원본 데이터는 Docker의 PostgreSQL 볼륨에, 실행 기록은 프로젝트의 `.decision-layer/runs.db`에 저장됩니다.

시작이 중단되어 컨테이너만 남았다면 다음 명령으로 멈춥니다.

```bash
decision-layer demo stop
```

포트가 이미 사용 중이거나 보관 위치를 바꾸려면 다음처럼 지정합니다.
선택한 포트는 다음 실행에도 사용합니다. `stop`에도 같은 `--directory`를 지정하세요.

```bash
decision-layer demo --directory ./sample_shop --port 8010 --cube-port 4110
```

## 내 Cube에 연결하기

이미 Cube가 있다면 Docker 샘플을 준비할 필요 없이 팀 프로젝트를 만듭니다.

```bash
decision-layer init my_team
cd my_team
decision-layer serve
```

[Cube 연결 가이드](./cube.md)에 따라 서버의 연결 주소와 인증을 설정합니다.
[Method 프로젝트](./method-projects.md)에서 팀의 Method와 Skill을 추가하는 방법을 확인하세요.

새로 만든 데모와 팀 프로젝트에는 기본 Skill과 Python Method 파일이 함께 생성됩니다. [프로젝트 파일과 테스트](./method-projects.md)에서 수정과 검사 방법을 확인하세요.

## AI로 재사용하기

[MCP 연결 가이드](./mcp.md)를 따라 사용하는 AI 클라이언트에 연결합니다.
기본 데모의 API 주소는 `http://127.0.0.1:8000`, Web 주소는 `http://127.0.0.1:8000/ui`입니다.

> 저장된 부문 분석 절차를 2026년 2월에 재사용해줘. 매출 1위 부문과 지역별 매출, 근거를 보여줘.

## 제품 개발에 참여하기

제품 소스나 관리자 화면을 수정하려면 [개발 환경](./development.md)을 준비하세요.
기존 전체 Docker 샘플은 [저장소 예제](https://github.com/haechangcho/decision-layer/tree/main/examples/quickstart)에서 실행할 수 있습니다.
