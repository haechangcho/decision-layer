# 프로젝트에 등록하기

함수와 등록 코드를 프로젝트에 저장하면 관리자 화면과 AI에서 사용할 수 있습니다.

## 프로젝트 만들기

[Decision Layer를 설치한 환경](quickstart.md)에서 실행합니다.

```bash
decision-layer init my_team
cd my_team
python -m pip install -e '.[test]'
```

수정할 수 있는 Skill 2개와 Python Method 2개가 생성됩니다.

```text
my_team/
├── decision-layer.yaml
├── pyproject.toml
├── recipes/
└── methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/
    │   ├── method.py
    │   ├── checks.py
    │   └── test_method.py
    └── matching/
        ├── method.py
        ├── checks.py
        └── test_method.py
```

- `SKILL.md`: AI가 따를 분석 절차
- `method.py`: 계산 함수와 `METHOD = python_method(...)` 등록 코드
- `checks.py`: 계산 전에 실행할 검사 함수. 필요할 때 사용
- `test_method.py`: 계산과 검사가 맞는지 확인하는 테스트

계산 함수와 등록 코드는 [Python Method 만들기](../tutorials/write-your-method)에서 살펴볼 수 있습니다.

## 수정하고 테스트하기

```bash
decision-layer check
decision-layer test
decision-layer list
decision-layer serve --reload
```

- `check`: 등록과 참조 검사. 분석은 실행하지 않습니다.
- `test`: 프로젝트 테스트 실행. 기본 계산 테스트는 Cube 없이 실행합니다.
- `list`: 등록된 Method와 파일 경로 확인
- `serve --reload`: 관리자 화면 실행. 파일을 수정하면 다시 읽습니다.

[Cube를 연결](cube.md)한 뒤 **분석 방법 → 입력 선택하고 테스트**에서 실행하세요.
계산을 바꾸면 테스트하고 Method 버전도 올립니다.

## Method 추가하기

```bash
decision-layer new python rank
decision-layer new skill metric_review
```

`methods/rank/method.py`와 `methods/metric_review/SKILL.md`가 생성됩니다.
기본 파일 없이 시작하려면 `decision-layer init my_team --empty`를 사용하세요.

## 검사 함수 연결하기

검사 함수는 선택 사항입니다. 짧으면 `method.py`에 두고, 길어지면 `checks.py`로 분리하세요.

```python
from .checks import check_data

METHOD = python_method(
    ols,
    name="my_team.ols",
    version="1.0.0",
    inputs={"data": DataInput(columns={...})},
    checks=[check_data],
)
```

**데이터 조회 → 기본 입력 검사 → 등록한 검사 → 계산** 순서로 실행합니다.
검사에서 `ValueError`가 발생하거나 `False`를 반환하면 계산을 멈추고 이유를 기록합니다.
자세한 조건은 [Method API](../reference/method-contract.md#검사와-오류)를 참고하세요.

## Skill 작성하기

`SKILL.md`에는 분석 순서와 판단 기준을 적습니다.

```markdown
# 매출을 항목별로 살펴보기

1. 상품 부문별 매출을 조회합니다.
2. 매출이 가장 큰 부문을 선택합니다. 공동 1위라면 사용자에게 확인합니다.
3. 선택한 부문의 매출을 매장별로 살펴봅니다.
4. 결과와 확인하지 못한 내용을 설명합니다.
```

도구 호출과 결과 기록은 공통 지침으로 전달하므로 각 Skill에 반복해서 적지 않습니다.

## AI에서 사용하기

서버를 켜 두고 [MCP를 연결](mcp.md)하세요. 같은 프로젝트의 Method를 찾아 실행할 수 있습니다.

## 팀에서 관리하기

프로젝트 파일을 Git으로 관리합니다. 패키지를 업데이트해도 작성한 파일은 유지됩니다.
서버는 `decision-layer serve --project /path/to/my_team`으로 프로젝트를 지정해 실행합니다.

Recipe는 `recipes/`, 실행 기록은 `.decision-layer/decision_layer.db`에 저장됩니다.
노트북의 로컬 실행 결과는 서버에 자동 저장되지 않습니다.
