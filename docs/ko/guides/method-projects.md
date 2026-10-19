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
from decision_layer.methods import Column, DataInput, python_method


def analyze(data, descending=True):
    """선택한 지표의 그룹별 순위를 계산합니다."""
    return data.assign(
        rank=data["value"].rank(method="min", ascending=not descending)
    )


METHOD = python_method(
    analyze,
    name="my_team.rank",
    version="1.0.0",
    inputs={"data": DataInput(columns={
        "value": Column(source="measure"),
        "group": Column(source="dimension"),
    })},
)
```

함수는 평소처럼 DataFrame으로 직접 실행할 수 있습니다. `METHOD`는 서버가 읽는
등록 대상입니다. 파일마다 `METHODS` 목록을 관리하거나 환경 변수에 모듈 이름을
하나씩 추가할 필요가 없습니다. 선언한 Column 이름과 함수 인자가 같으면
조회한 열 이름을 자동으로 전달합니다. 실제 지표와 기간은 실행할 때 연결합니다.

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

## 4. 관리자 화면과 AI에서 사용하기

프로젝트의 함수를 서버에서 읽으면 Web과 REST, MCP에서 사용할 수 있습니다.

[만든 Method를 서비스에서 사용하기](./method-deployment.md)에서 다음 단계를 이어서 확인하세요.

- 프로젝트를 지정해 서버와 관리자 화면 실행하기
- Cube를 연결하고 실제 데이터로 테스트하기
- MCP로 AI에 연결하고 Run 확인하기
- Python에서 실제 Cube 데이터로 실행하기
- 코드 수정, 배포, 저장 위치 관리하기

기존 `DL_METHOD_MODULES`의 `METHODS` export와 `DL_SKILLS_DIR`도 지원합니다.
같은 자산을 프로젝트와 기존 설정 양쪽에 중복 등록하지 않도록 확인하세요.
