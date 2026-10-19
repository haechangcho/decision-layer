# 프로젝트에서 Method 사용하기

[앞에서 만든 함수](methods.md)를 프로젝트에 저장하면 관리자 화면과 AI에서도 사용할 수 있습니다.
같은 프로젝트 파일을 Python, CLI와 서버가 읽습니다.

## 프로젝트와 파일 만들기

Decision Layer를 [설치한 환경](quickstart.md)에서 실행합니다.

```bash
decision-layer init my_team
cd my_team
decision-layer new python rank
```

```text
my_team/
├── decision-layer.yaml
└── my_team/methods/rank/
    └── method.py
```

`method.py`에 계산 함수와 `METHOD = python_method(...)`를 둡니다.
CLI가 만든 함수는 `analyze`라는 이름의 순위 예제이며, 내용을 바꿔 사용할 수 있습니다.
보조 Python 파일은 같은 폴더에 두고 import합니다.

분석 지침을 Skill로 등록하려면 다음처럼 파일을 만듭니다.

```bash
decision-layer new skill metric_review
```

생성된 `my_team/methods/metric_review/SKILL.md`에 이름, 버전, 설명과 지침을 작성합니다.
기존 Method의 실행 순서를 재사용하려면 [Recipe](recipes.md)를 만드세요.
[완성 프로젝트](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)에는 순위 함수, OLS와 Skill이 있습니다.

## 등록 확인과 서버 실행

```bash
decision-layer check
decision-layer list
decision-layer serve --reload
```

- `check`: 등록 코드와 참조를 검사합니다. 데이터 조회와 계산은 실행하지 않습니다.
- `list`: 이름, 버전, 종류와 원본 파일 경로를 보여줍니다.
- `serve`: 프로젝트의 Method를 읽어 관리자 화면과 API를 실행합니다.

터미널에 표시된 관리자 화면 주소를 엽니다. 기본 주소는 `http://127.0.0.1:8000/ui/`입니다.
파일을 수정하면 `--reload`가 서버를 다시 시작합니다. 다른 위치에서는
`decision-layer serve --project /path/to/my_team`으로 프로젝트를 지정합니다.

## 관리자 화면에서 테스트하기

[Cube 연결](cube.md)을 준비한 뒤 다음 순서로 실행합니다.

1. **분석 방법**에서 등록한 Method를 선택합니다.
2. **입력 선택하고 테스트**에서 지표, 차원과 기간을 선택합니다.
3. 결과와 검증 내역을 확인하고 **실행 기록**에서 쿼리와 입력을 다시 봅니다.

노트북의 예제 데이터와 로컬 결과는 서버에 자동으로 업로드되지 않습니다.
서버는 연결된 Cube에서 실제 데이터를 조회합니다.

## AI에서 사용하기

[MCP 연결](mcp.md)에 따라 같은 API에 연결합니다. 기본 서버의 주소는 다음과 같습니다.

```text
DL_API_URL=http://127.0.0.1:8000
DL_WEB_URL=http://127.0.0.1:8000/ui
```

AI는 등록된 Method와 입력 조건을 확인하고 semantic catalog에서 데이터를 선택합니다.
실행한 입력, 결과와 쿼리는 서버의 Run에 남습니다.

## 팀에서 관리하기

프로젝트 파일은 팀의 Git 저장소에서 관리하고, 서버에는 검토한 파일과 Python 의존성을 배포합니다.
`DL_PROJECT_DIR`로 프로젝트 경로를 지정하고 서버를 다시 시작하면 같은 Method를 읽습니다.

실행 기록은 `.decision-layer/decision_layer.db`, Recipe는 `recipes/`에 저장됩니다.
노트북, CLI와 서버는 같은 로더를 사용하지만 실행 기록은 각 환경에 따로 남습니다.
Web에서 발행한 버전은 별도 관리되며 프로젝트 원본 파일을 덮어쓰지 않습니다.
