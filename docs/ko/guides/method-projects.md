# 프로젝트에 등록하기

[예제에서 본 함수](../tutorials/write-your-method)를 프로젝트에 저장하면 관리자 화면과 AI에서도 사용할 수 있습니다.
같은 프로젝트 파일을 Python, CLI와 서버가 읽습니다.

## 프로젝트 만들기

Decision Layer를 [설치한 환경](quickstart.md)에서 실행합니다.

```bash
decision-layer init my_team
cd my_team
python -m pip install -e '.[test]'
```

기본 Skill 2개와 Python Method 2개가 수정 가능한 파일로 생성됩니다.

```text
my_team/
├── decision-layer.yaml
├── pyproject.toml
└── my_team/methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/
    │   ├── method.py
    │   └── test_method.py
    └── matching/
        ├── method.py
        └── test_method.py
```

- `SKILL.md`: AI가 따라야 할 조회와 분석 지침입니다.
- `method.py`: 계산 함수와 `METHOD = python_method(...)` 등록 코드입니다.
- `test_method.py`: 정답을 아는 합성 데이터와 잘못된 입력으로 계산을 검사합니다.
- `pyproject.toml`: 프로젝트에 필요한 패키지를 관리합니다.

OLS는 statsmodels, 매칭은 scikit-learn으로 계산합니다. 결과는 관측된 연관성과 집단 차이이며, 인과관계를 입증하지 않습니다.

## 검사하고 실행하기

```bash
decision-layer check
decision-layer test
decision-layer list
decision-layer serve --reload
```

| 명령 | 확인할 내용 |
|---|---|
| `check` | 파일을 읽고 등록과 참조를 검사합니다. 계산은 실행하지 않습니다. |
| `test` | OLS와 매칭의 테스트 13개를 실행합니다. Cube나 서버가 필요하지 않습니다. |
| `list` | 등록한 이름, 버전과 원본 파일 경로를 보여줍니다. |
| `serve` | 같은 프로젝트로 관리자 화면과 API를 실행합니다. |

기본 이름은 `analysis.metric_lookup`, `analysis.drilldown`, `stats.regression_adjustment`, `stats.binary_matching`입니다.
새 프로젝트는 이 파일만 기본 목록에 등록합니다. 필요 없는 폴더는 삭제해도 됩니다.

터미널에 표시된 관리자 화면 주소를 엽니다. 기본 주소는 `http://127.0.0.1:8000/ui/`입니다.
파일을 수정하면 `--reload`가 서버를 다시 시작합니다. 계산을 바꾸면 테스트를 실행하고 Method 버전도 올리세요.
다른 위치에서는 `decision-layer serve --project /path/to/my_team`으로 프로젝트를 지정합니다.

## Method 추가하기

```bash
decision-layer new python rank
decision-layer new skill metric_review
```

각각 `my_team/methods/rank/method.py`와 `my_team/methods/metric_review/SKILL.md`를 만듭니다.
여러 Method의 실행 순서를 재사용하려면 [Recipe](recipes.md)를 만드세요.
기본 파일 없이 시작하려면 `decision-layer init my_team --empty`를 사용합니다.

## 관리자 화면에서 테스트하기

[Cube 연결](cube.md)을 준비한 뒤 다음 순서로 실행합니다.

1. **분석 방법**에서 등록한 Method를 선택합니다.
2. **입력 선택하고 테스트**에서 지표, 차원과 기간을 선택합니다.
3. 결과와 검증 내역을 확인하고 **실행 기록**에서 쿼리와 입력을 다시 봅니다.

서버는 연결된 Cube에서 실제 데이터를 조회하고 Run을 기록합니다.

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

패키지를 업데이트해도 프로젝트 파일은 덮어쓰지 않습니다. 기존 프로젝트에 기본 파일을 자동으로 추가하지도 않습니다.
처음 설치 흐름을 다시 확인하려면 새 폴더에서 `init`을 실행하세요.
이전 설정 파일은 기존 기본 Method를 유지하며, 새 설정은 `include_builtin_methods: false`로 프로젝트 파일을 기준으로 등록합니다.
