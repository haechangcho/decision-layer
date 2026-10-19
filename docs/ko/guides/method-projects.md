# Method 프로젝트 만들기

Python Method와 Skill은 **한 프로젝트의 같은 `methods/` 폴더**에서 관리합니다.
정해진 파일을 추가하면 로컬 Python, CLI, 서버가 같은 로더로 읽습니다.

## 0. 설치부터 시작하기

Python 3.11 이상과 프로젝트 CLI가 포함된 Decision Layer 저장소가 필요합니다.
연습 폴더를 만들고 별도의 가상환경에 현재 저장소 코드를 설치합니다.

```sh
mkdir -p ~/Workspace/dl-method-lab
cd ~/Workspace/dl-method-lab
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '/path/to/decision-layer[stats]'
decision-layer --help
```

`/path/to/decision-layer`는 실제 저장소의 절대 경로로 바꿉니다. `[stats]`는 예제의
DataFrame 계산에 필요한 pandas 등을 설치합니다. 현재 개발 중인 CLI를 사용하므로
수정한 저장소에서 설치해야 합니다. 새 터미널에서는 위 가상환경을 다시 활성화합니다.

## 1. 프로젝트와 파일 생성

Decision Layer가 설치된 환경에서 실행합니다. 저장소 개발 환경에서는
`python -m decision_layer`로도 같은 명령을 실행할 수 있습니다.

```sh
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer new skill metric_review
```

```text
my_team/
├── decision-layer.yaml           # 프로젝트 이름: my_team
└── my_team/                      # import 가능한 Python 패키지
    └── methods/
        ├── rank/
        │   └── method.py         # 일반 함수 + METHOD 객체 하나
        └── metric_review/
            └── SKILL.md          # YAML 메타데이터 + 분석 지침
```

자동 생성된 `__init__.py`는 생략한 구조입니다. Python 진입 파일은 `method.py`,
Skill 진입 파일은 대문자 `SKILL.md`입니다. 그 외의 보조 파일을 Method로 수집하지
않습니다. 한 폴더에는 둘 중 하나만 둡니다.

## 2. 함수 또는 Skill 수정

`my_team/methods/rank/method.py`에는 다음이 들어 있습니다.

```python
from decision_layer.methods import DataInput, python_method


def analyze(data, descending=True):
    """선택한 지표의 그룹별 순위를 계산합니다."""
    return data.assign(
        rank=data["value"].rank(method="min", ascending=not descending)
    )


METHOD = python_method(
    analyze,
    name="my_team.rank",
    version="1.0.0",
    output="table",
    inputs={"data": DataInput(measures=["value"], dimensions=["group"])},
)
```

함수는 평소처럼 DataFrame으로 직접 실행할 수 있습니다. `METHOD`는 서버가 읽는
등록 대상입니다. 파일마다 `METHODS` 목록을 관리하거나 환경 변수에 모듈 이름을
하나씩 추가할 필요가 없습니다. 함수가 컬럼 이름도 인자로 받는 경우에만
`DataInput.column_args`를 지정합니다. 실제 지표·기간은 실행할 때 연결합니다.

생성된 함수는 `analyze`입니다. 프로젝트 루트(`decision-layer.yaml`이 있는 곳)에서
작은 DataFrame으로 직접 확인할 수 있습니다.

```sh
python - <<'PY'
import pandas as pd
from my_team.methods.rank.method import analyze

data = pd.DataFrame({"group": ["A", "B", "C"], "value": [30, 20, 20]})
print(analyze(data).to_string(index=False))
PY
```

자동 생성한 코드라면 `rank` 열은 `1.0, 2.0, 2.0`입니다. 계산 코드를 바꾼 뒤 같은
명령으로 결과를 비교합니다.

Skill은 `SKILL.md`의 이름·버전·설명과 본문을 수정합니다. 새 템플릿은 기록된 Cube
조회로 실행하는 Skill입니다. Python 계산이나 분석 품질 검증을 지침으로 대신하지
않습니다. 실행 순서를 고정하려면 기존 Method를 Recipe로 조합합니다.

## 3. 등록 결과 검사

```sh
decision-layer check
decision-layer list
decision-layer list --json
```

`list`는 **이름·버전·종류·원본 파일 경로**를 보여줍니다. 기본 Method와 내가 추가한
Method를 함께 확인할 수 있습니다. `check`는 등록과 Skill 참조를 검사합니다.
실제 Cube 조회나 계산 정확성은 실행 테스트로 별도 확인해야 합니다. 중복 이름,
잘못된 Python export, 잘못된 Skill은 파일 경로를 포함한 오류로 중단됩니다.

노트북에서도 동일한 프로젝트를 읽습니다.

```python
session.load_project("/path/to/my_team")
session.list_methods()
session.find_methods(names=["my_team.rank"])
```

프로젝트 로딩은 현재 세션의 목록에 추가합니다. 서버로 업로드하지 않습니다.
코드 변경 후에는 커널을 다시 시작하거나 새 프로세스로 검사합니다.

## 4. 서버와 AI에서 사용

```sh
decision-layer serve --reload
```

현재 디렉터리와 상위 디렉터리에서 `decision-layer.yaml`을 찾아 프로젝트를
읽습니다. 다른 위치에서는 `--project /path/to/my_team`을 지정합니다. 서버가
시작하면 파일의 Method가 기존 Registry에 등록되어 Web·REST·MCP에 나타납니다.
`--reload`는 로컬 개발용이며 Python·Skill·설정 변경 시 API를 다시 시작합니다.
별도 DB 설정이 없으면 프로젝트의 `.decision-layer/decision_layer.db`에 실행 기록을
저장합니다. `DL_DATABASE_URL`을 지정하면 해당 저장소를 사용합니다.

운영에서는 검토한 프로젝트 파일과 Python 의존성을 서버에 배포하고
`DL_PROJECT_DIR=/opt/my_team`으로 **프로젝트 경로 하나**를 지정한 뒤 재시작합니다.
컨테이너를 쓰면 그 경로에 프로젝트를 복사하거나 읽기 전용으로 마운트합니다.
CLI는 API를 시작하며 Web과 MCP 클라이언트는 기존 연결 설정을 사용합니다.

AI는 `list_methods`로 목록을 보고 `describe_method`로 입력 조건을 확인합니다.
`find_methods`는 요구 조건에 따른 후보를 반환하며 분석 의미를 자동 확정하지
않습니다. 서버 실행은 기존 Run 엔진에서 입력·버전·쿼리·결과를 기록합니다.
등록 코드는 프로젝트 파일에 남고 서버는 시작할 때 그 목록을 다시 만듭니다.

기존 `DL_METHOD_MODULES`의 `METHODS` export, `DL_SKILLS_DIR`, 관리형 Web 게시 자산은
계속 지원합니다. 같은 이름을 두 곳에서 등록하면 오류가 나므로 새 프로젝트로
이관한 자산은 이전 등록 설정에서 제거합니다.

[완성 프로젝트](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)
에는 순위 계산, OLS, Skill이 함께 있습니다. 저장소에서 아래처럼 바로 검사합니다.

```sh
python -m decision_layer check --project examples/methods/project
python -m decision_layer list --project examples/methods/project
```


## 설치한 프로젝트의 관리자 화면 열기

Python 패키지에는 관리자 화면이 포함됩니다. 프로젝트 폴더에서 실행하세요.

```sh
python -m pip install "decision-layer[stats]==0.1.0a2"
decision-layer serve --reload
```

터미널에 표시된 `http://127.0.0.1:8000/ui/`를 열면 현재 프로젝트의
Method 목록과 상세, Recipe, Run, 연결 설정을 확인할 수 있습니다. Node.js나
제품 소스 저장소는 필요하지 않습니다. 프로젝트 Method는 파일에서 수정하고
관리자 화면에서 입력을 선택해 테스트합니다. 실제 데이터 조회에는 Cube 연결과
기존 인증 설정이 필요합니다. Web 편집은 별도로 허용한 환경에서만 사용할 수
있으며 프로젝트 파일을 직접 덮어쓰지 않습니다.

실행 기록은 기본적으로 `.decision-layer/decision_layer.db`, Recipe는
`recipes/`에 저장됩니다. 기존 환경 변수 설정은 유지됩니다. API만 필요한
개발자는 `decision-layer serve --api-only`를 사용할 수 있습니다.
