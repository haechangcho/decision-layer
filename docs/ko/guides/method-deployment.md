---
title: 만든 Method를 서비스에서 사용하기
description: 노트북에서 만든 함수를 프로젝트에 저장하고 Web과 MCP에서 실행합니다.
---

# 만든 Method를 서비스에서 사용하기

노트북에서 만든 함수를 관리자 화면과 AI에서도 사용하려면 프로젝트 파일로 저장하고 서버를 실행합니다.

`session.register(...)`는 현재 Python 세션에만 등록합니다. 서버는 프로젝트 파일을 읽어 별도로 등록하며, 서버에서 실행한 입력과 결과를 Run에 기록합니다.

## 1. 함수와 등록 코드를 파일로 저장하기

Decision Layer가 설치된 환경에서 프로젝트를 만듭니다. 이미 만든 프로젝트가 있으면 그 폴더에서 작업하세요.

```sh
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer new python ols
decision-layer new skill metric_review
```

```text
my_team/
├── decision-layer.yaml
└── my_team/methods/
    ├── rank/method.py
    ├── ols/method.py
    └── metric_review/SKILL.md
```

파일마다 실행할 함수와 등록 코드를 함께 둡니다. 서버가 읽는 등록 객체의 이름은 `METHOD`입니다. 노트북의 `rank_method`를 파일에서는 `METHOD`라는 이름으로 저장하는 것입니다.

예를 들어 `my_team/methods/rank/method.py`는 다음과 같습니다.

```python
from decision_layer.methods import Column, DataInput, python_method


def rank_values(data, descending=True):
    """선택한 지표의 그룹별 순위를 계산합니다."""
    return data[["group", "value"]].assign(
        rank=data["value"].rank(method="min", ascending=not descending).astype(int)
    )


METHOD = python_method(
    rank_values,
    name="my_team.rank",
    version="1.0.0",
    inputs={
        "data": DataInput(
            columns={
                "value": Column(source="measure"),
                "group": Column(source="dimension"),
            },
        ),
    },
)
```

OLS도 같은 방식으로 `ols/method.py`에 함수와 등록 코드를 넣습니다. Skill은 `SKILL.md`에 메타데이터와 분석 지침을 작성합니다. 자세한 파일 규칙과 설치 방법은 [Method 프로젝트](./method-projects.md)에 있습니다.

이 문서의 `Column`과 `role="entity_key"` 예제는 최신 저장소 코드를 기준으로 합니다. 해당 API가 포함된 배포 버전을 사용하거나, 저장소를 설치한 개발 환경에서 실행하세요. 관리자 화면이 포함된 기존 PyPI 버전만 설치했다고 최신 입력 API까지 제공되는 것은 아닙니다.

## 2. 등록을 확인하고 서버 실행하기

프로젝트 폴더에서 실행합니다.

```sh
decision-layer check
decision-layer list
decision-layer serve --port 8010 --reload
```

- `check`: 등록 코드와 참조를 검사합니다. 데이터 조회나 계산은 실행하지 않습니다.
- `list`: 등록된 이름, 버전, 종류, 파일 경로를 보여줍니다.
- `serve`: 현재 프로젝트의 Method를 읽고 관리자 화면과 API를 실행합니다.

터미널을 실행한 채 [관리자 화면](http://127.0.0.1:8010/ui/)을 엽니다. **분석 방법**에서 `my_team.rank`와 `my_team.ols`를 확인할 수 있습니다. 8010 포트가 사용 중이면 다른 포트를 선택하세요.

다른 위치에서 실행하려면 프로젝트를 지정합니다.

```sh
decision-layer serve --project /path/to/my_team --port 8010 --reload
```

`--reload`는 개발 중 파일이 바뀌면 서버를 다시 시작합니다. 변경 후 관리자 화면을 새로고침하세요. 운영 환경에서는 검토한 프로젝트 파일과 Python 의존성을 배포하고 서버를 재시작합니다. `DL_PROJECT_DIR`로 프로젝트 경로를 지정할 수도 있습니다.

### 준비된 예제 프로젝트로 확인하기

저장소의 [완성 프로젝트](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)에는 `workshop_project.rank`, `workshop_project.ols`, Skill이 있습니다. 저장소 루트에서 실행합니다.

```sh
decision-layer check --project examples/methods/project
decision-layer list --project examples/methods/project
decision-layer serve --project examples/methods/project --port 8010 --reload
```

Python에서도 같은 파일을 읽을 수 있습니다. 노트북의 테스트 데이터로 프로젝트 로딩만 확인하려면 다음처럼 실행합니다.

```python
from examples.methods.authoring.plain_python import practice_session
from decision_layer.methods import Scope

project_session = await practice_session()
project_session.load_project("examples/methods/project")  # 저장소 루트 기준

project_trial = await project_session.run(
    "workshop_project.rank",
    bindings={
        "value": "cube://fixture/sales/revenue",
        "group": "cube://fixture/sales/product",
    },
    scope=Scope(
        date_range=("2026-09-01", "2026-09-30"),
        time_dimension="cube://fixture/sales/date",
    ),
)

project_trial.result.primary.data
```

CLI, Python, 서버는 같은 프로젝트 로더를 사용합니다. 이 로컬 실행 결과가 서버에 자동으로 업로드되지는 않습니다.

## 3. 관리자 화면에서 실제 데이터로 테스트하기

서버에서 실행하려면 [Cube 연결](./cube.md)과 인증을 먼저 준비합니다. 노트북의 예제 데이터가 서버에도 자동으로 연결되지는 않습니다.

1. **연결 설정**에서 사용할 Cube를 연결합니다.
2. **분석 방법**에서 Method를 선택하고 **입력 선택하고 테스트**를 누릅니다.
3. 필요한 지표와 차원을 연결합니다. OLS에서는 개체 키, 결과 변수, 관심 변수, 함께 고려할 변수를 선택합니다.
4. 날짜 기준과 조회 기간, 계산 옵션을 지정하고 실행합니다.
5. 결과와 검사 내역, 경고, 실제 쿼리를 확인합니다. 서버 실행은 **실행 기록**에서 다시 볼 수 있습니다.

Recipe를 저장하기 전에도 테스트할 수 있습니다. 반복 사용할 입력과 분석 절차는 [Recipe](./recipes.md)로 저장하세요.

### 코드를 수정할 때

프로젝트 Method의 원본은 `method.py`입니다. 파일을 수정한 뒤 다시 검사하고 실행합니다.

Web에서 코드를 보거나 편집하려면 서버의 인증과 편집 권한이 필요합니다. 편집을 허용한 환경에서는 **초안 저장 → 등록 검사 → 검토 → 새 버전 발행**으로 진행합니다. 이 과정은 프로젝트 원본 파일을 덮어쓰지 않습니다. 테스트는 설치되거나 발행된 코드를 실행하며, 저장하지 않은 편집 내용을 실행하지 않습니다.

## 4. MCP로 AI에게 요청하기

[AI 도구 연결](./mcp.md)에 따라 MCP를 실행 중인 API에 연결합니다. 위 예제 서버를 사용한다면 다음 주소를 설정합니다.

```text
DL_API_URL=http://127.0.0.1:8010
DL_WEB_URL=http://127.0.0.1:8010/ui
```

MCP 실행 환경에는 Decision Layer의 `mcp` 선택 의존성이 필요합니다. 회사 Cube에 접근할 때는 연결 가이드에 따라 인증도 설정합니다.

AI는 `list_methods`나 `find_methods`로 등록된 Method를 찾고, `describe_method`로 입력 조건을 확인합니다. 이어 `search_semantic`으로 실제 지표와 차원을 찾아 연결하고 Run 안에서 실행합니다. 변수나 기간의 의미가 모호하면 실행 전에 사용자에게 확인합니다.

예를 들어 다음처럼 요청할 수 있습니다.

> `my_team.ols`로 고객별 광고 노출 횟수와 구매 금액의 관계를 분석해줘. 나이와 이전 구매 금액을 함께 고려하고 싶어. 등록된 입력 조건과 catalog를 확인하고, 분석 단위나 기간이 불분명하면 먼저 물어봐. 실행한 입력, 결과, 검사 내역과 Run 링크를 알려줘.

기본 Method를 재사용하려면 다음과 같이 요청합니다.

> `stats.regression_adjustment`와 `stats.binary_matching`의 입력 조건을 확인해줘. 분석할 변수와 단위, 기간을 확인하고 적합한 Method로 실행해줘. 결과와 검사 내역, 경고, Run 링크를 알려줘. 인과관계가 입증됐다고 단정하지 마.

기본 통계 Method는 해당 버전이 요구하는 추가 패키지가 설치되어 있어야 합니다. 각 분석의 조건과 한계는 [선택 고급 분석](./statistical-methods.md)을 참고하세요.

노트북의 합성 데이터 실행은 계산 흐름을 확인하는 단계입니다. 실제 AI의 입력 선택과 Cube 조회는 연결 후 Run에서 확인합니다.

## 5. Python에서 실제 Cube 데이터로 실행하기

노트북의 함수도 실제 Cube에 연결한 `MethodSession`에 등록해 실행할 수 있습니다. 실행 환경에 `CUBE_API_URL`과 `CUBE_TOKEN`을 설정하고, 토큰을 코드나 출력에 남기지 마세요.

```python
import os
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.semantic.credentials import RequestCredentials

live = await MethodSession.cube(
    os.environ["CUBE_API_URL"],
    RequestCredentials(os.environ["CUBE_TOKEN"]),
    instance=os.environ.get("CUBE_INSTANCE", "local"),
)

[(item.ref, item.title) for item in live.metrics()]
```

차원도 확인합니다.

```python
[(item.ref, item.title) for item in live.dimensions()]
```

아래는 기존 노트북에서 만든 `rank_method`를 실행하는 예시입니다. 지표, 차원, 날짜 식별자와 기간은 위에서 확인한 실제 값으로 바꿉니다. `shop`이라는 연결 이름만 지정한다고 예제 객체가 생성되지는 않습니다.

```python
live.register(rank_method)

live_trial = await live.run(
    "my_team.rank",
    bindings={
        "value": "cube://shop/sales/revenue",
        "group": "cube://shop/sales/product",
    },
    scope=Scope(
        date_range=("2026-02-01", "2026-02-28"),
        time_dimension="cube://shop/sales/date",
    ),
)

live_trial.result.primary.data
```

이 실행은 로컬 Python 세션에서 수행합니다. 관리자 화면에서 Run을 확인하려면 서버의 Web, REST 또는 MCP를 통해 실행하세요.

## 6. 패키지와 데이터는 어디에 저장되나요?

| 대상 | 관리 위치 |
|---|---|
| 제품 Python 코드와 관리자 화면 | 설치한 Decision Layer 패키지 |
| 팀의 Method와 Skill | 프로젝트의 `methods/` 폴더 |
| 서버 실행 기록, 결과, 연결 설정 | 기본적으로 `.decision-layer/decision_layer.db` |
| Recipe | 기본적으로 `recipes/` |
| Web에서 발행한 Method 버전 | 기본적으로 `.decision-layer/method-assets/` |
| 분석할 원본 데이터와 semantic 모델 | 회사의 데이터 저장소와 Cube |

관리자 화면의 소스는 제품 Git 저장소에서 관리합니다. 배포할 때 빌드한 HTML, JavaScript, CSS를 Python 패키지에 포함하므로, 패키지를 사용하는 데 Node.js나 Docker는 필요하지 않습니다.

SQLite는 서버의 기록을 저장하는 내부 DB입니다. 회사의 원본 데이터를 대신하지 않습니다. 같은 저장소를 사용하면 서버를 재시작해도 기록이 유지됩니다. `DL_DATABASE_URL` 등 기존 저장소 설정이 있으면 그 설정을 우선 사용합니다.

## 다음으로 해볼 것

- `descending=False`로 순위를 바꾸고 직접 함수 실행과 Method 실행을 비교합니다.
- OLS에 계산 옵션을 추가하고 기본값이나 타입 힌트로 입력 조건이 생성되는지 확인합니다.
- catalog에서 변수를 하나 더 선택하고 분석에 포함할 이유를 검토합니다.
- 빈 데이터, 중복 개체 키, 결측값, 중복 설명변수로 실패 사례를 확인합니다.

숫자는 estimate, DataFrame과 행 목록 및 dict는 table로 처리합니다. dict의 `value`를 대표 추정치로 쓰면 `output="estimate"`를 지정합니다. 라이브러리 결과 객체를 정리하려면 `adapt=함수`를 사용할 수 있습니다. 함수 설명에는 용도와 분석 가정, 해석 한계를 적습니다. 설명문 자체가 검사를 대신하지는 않습니다.
