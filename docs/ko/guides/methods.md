# 첫 Method 개발

Method는 하나의 분석 기능입니다. 기존 Method 조합이나 설정으로 충분하면 Recipe를
작성합니다. 처음 시작할 때 필요한 것은 Python 3.11+입니다.

## 설치와 첫 테스트

저장소를 내려받고 실행합니다.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
make setup
make example
```

::: details Make 없이 실행하기

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q examples/methods/first_method
```
:::

[첫 Method 예제](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/first_method)에서 시작합니다.

| 파일 | 역할 |
| --- | --- |
| `method.py` | 입력 명세와 분석 구현 |
| `fixtures.py` | 예상 semantic query와 독립적인 응답 데이터 |
| `test_method.py` | 예상 정답 검사 |
| `explore.ipynb` | 선택적으로 실제 Cube에서 탐색 |

구현을 수정하고 테스트를 다시 실행합니다. 예상 그룹값은 30·20·10이며,
기간·차원·정렬·조회 수가 기대한 것과 같은지 확인합니다.
웹 서버, 실제 source, 인증 정보, Docker가 필요하지 않습니다.

## 코드 이해하기

```python
from decision_layer.methods import (
    Method, MethodOutput, MethodManifest, RoleSpec, ParamSpec, Artifact, DatasetSpec,
)
```

`manifest`는 입력 역할·파라미터·출력·해석 수준을 선언합니다.
`run(ctx, bindings, params)`는 `ctx.dataset()`으로 조회하고 `MethodOutput`을 반환합니다.
지표 수식·join·권한은 semantic source가 관리합니다. 반환하는 모든 artifact 타입을
명세에 선언해야 합니다. 공통 Registry가 선언되지 않은 출력을 거절합니다.

## 여러 쿼리 조합

```bash
.venv/bin/python -m pytest -q examples/methods/peer_comparison
```

제품의 `methods/peer_comparison.py`를 import해 대상, 대상을 제외한 peers,
대상을 제외한 전체 비교군을 각각 조회합니다. fixture의 12%·8%·6%에서 차이는
4·6%p입니다. 통계적 유의성이나 인과효과를 주장하지 않습니다.
여러 조회와 조합은 하나의 Method 안에서 수행할 수 있습니다.

실패·예산·출력 계약은 다음 테스트에서 확인합니다.

```bash
.venv/bin/python -m pytest -q tests/unit/test_method_dev.py
```

## 실제 데이터 연결

```python
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from decision_layer.semantic.credentials import RequestCredentials

session = await MethodSession.cube(cube_url, RequestCredentials(token))
session.metrics()
session.dimensions(metric_ref)
session.register(my_method)
trial = await session.run(
    my_method.manifest.name, bindings=bindings, params=params,
    scope=Scope(date_range=("2026-09-01", "2026-09-30"), time_dimension=time_ref),
)
trial.result
trial.attempts
trial.queries
```

catalog에서 실제 참조를 선택합니다. 선언된 차원 관계는 탐색 정보이고,
실제 조합은 provider가 검증합니다. 인증 정보는 노트북 셀과 출력에 저장하지 않습니다.
직접 실행은 현재 이벤트 루프에서 동작해 breakpoint를 사용할 수 있습니다.
provider·코드 예외는 다시 발생하고 `session.last_trial.attempts`에 중간 근거가 남습니다.
직접 실행은 저장된 Run을 만들지 않습니다.

`session.preview(recipe, step_index=..., scope=...)`는 기존 RunEngine으로 새 prefix를
실행하며 worker와 로컬 메모리 저장소를 사용합니다. 원격 웹 서버로 업로드하지 않습니다.
사용 후 `session.close()`를 호출합니다. 수정한 구현은 `replace=True`로 등록하고,
모델 변경 후 `refresh_catalog()`로 갱신합니다. 예제 노트북에서 2단계 실행을 확인할 수 있습니다.

## 등록과 기여

검토할 구현을 `src/decision_layer/methods/`에 추가하고 `__init__.py`의
`register_builtins()` 목록에 연결합니다. 각 모듈은 import만으로 자신을 등록하지 않습니다.
`query.peer_comparison` 같은 등록 ID는 폴더 구조와 독립적입니다.

관련 테스트와 `make test`를 실행한 뒤 구현·명세·독립적인 정답·실패 테스트·호출 예제를
함께 PR로 제출합니다. 라이브러리 의존성은 명시적으로 선언하고 실행 중 설치하지 않습니다.

[입출력 계약 참고](../reference/method-contract.md)와 [테스트 가이드](testing.md)를 확인하세요.
