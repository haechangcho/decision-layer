# 일반 Python으로 작성하는 통계 Method

새 Method는 데이터 역할을 선언하고 라이브러리의 원래 API를 사용합니다. `AnalysisDesign` 객체·가정별 checkbox·seed 입력·manifest 직접 조작은 필요하지 않습니다. Python 호출도 함수 인자와 같은 이름을 사용합니다. semantic 권한·scope·제한·provenance는 내부 실행 계약이 관리합니다.

## 한 번 설치

선택적 라이브러리는 개발·서버 환경에 설치하며 Method 실행 중 설치하지 않습니다. 검증한 Python 3.11 constraints를 사용하고 실제 runtime 버전을 기록합니다.

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/patterns/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
```
## 등록하고 사용

새 fixture session 또는 실제 Cube 연결을 사용합니다. 데이터 역할은 outcome·treatment·confounders·unit 네 가지이며 현재 기간과 공통 필터는 실행 scope에 속합니다.

```python
from decision_layer.methods import Scope, register_builtins
from examples.methods.patterns.scenarios import M, TREAT, BASELINE, UNIT, DATE, FEB

register_builtins(session.registry)
trial = await session.run(
    "stats.binary_regression",  # Use "stats.linear_dml" for constant binary DML.
    outcome=M,
    treatment=TREAT,
    confounders=[BASELINE],
    unit=UNIT,
    scope=Scope(FEB, DATE),
)
print(trial.result.primary.data)
```
measure인 교란변수도 `confounders`에 직접 넣습니다. catalog를 보고 native measure와 dimension을 구분합니다. REST/MCP와 기존 Recipe용 입력 map·canonical bindings도 계속 지원합니다.

## 라이브러리의 원래 API로 작성

일반 Python 계산 함수를 작성하고 `ctx.entities`로 데이터를 조회한 뒤 `ctx.compute`로 계산합니다. 같은 함수에 DataFrame을 직접 넣어 독립적으로 실행할 수 있습니다. DoWhy 호출은 코드에 그대로 남습니다.

```python
from dowhy import CausalModel

model = CausalModel(data=observations, treatment="treatment", outcome="outcome", graph=graph)
estimand = model.identify_effect(proceed_when_unidentifiable=False)
estimate = model.estimate_effect(
    estimand, method_name="backdoor.linear_regression",
    control_value=0, treatment_value=1, target_units="ate", confidence_intervals=False,
)
```

`examples/methods/patterns/write_your_method.ko.ipynb`에는 원래 DoWhy 계산과 짧은 Method 연결 코드가 있습니다. 서버에서 사용할 함수는 검토한 import 가능한 Python 모듈에 저장합니다. 범용 estimator facade는 필요하지 않습니다.

<<< @/../src/decision_layer/methods/advanced.py#binary_regression

## 데이터 검사와 해석

primary unit·유일한 non-null key·유한값·결측·처치군·인코딩 제한·회귀 rank·관측 지원 범위를 검사합니다. 이진 회귀는 군별 최소 30개와 적합 propensity [0.05, 0.95]를 요구하지만 이는 진단 기준이며 positivity 증명이 아닙니다. DML은 해당 모형의 적합 조건을 검사합니다. 부족한 데이터는 거절합니다.

검토된 Method는 항상 연관성으로 보고하며 `assumptions_status="not_verified"`, `causal_claim="not_established"`를 기록합니다. 해당하는 그래프·estimator·대비·고정 seed/fold·진단을 결과에 남기고 신뢰구간은 제공하지 않습니다. 그래프·refutation·설명만으로 식별이 성립하지 않습니다. 인과 주장에는 처치·교란변수 시점, 미측정 교란, 독립성·간섭 등에 대한 근거가 필요합니다. 설명은 검증이나 semantic 정의를 덮어쓰지 않습니다.

## 두 기간의 집단 변화 비교

`stats.two_period_contrast`는 정확히 두 개의 순서가 있는 bucket, 고정 처치군, 유한 outcome을 가진 완전한 unit × time panel을 요구합니다. 앞 bucket을 pre, 뒤 bucket을 post로 사용하며 더 긴 panel의 양끝을 임의 선택하지 않고 거절합니다. 평행 추세는 주장하지 않습니다. 선택적 `windows`는 겹치지 않는 추출 분할, `granularity`는 month/day bucket을 지정합니다. 가정 checkbox가 아닌 실제 데이터 형태에 필요한 입력입니다.

## 호환성

`stats.adjusted_difference`·`stats.dml`·`stats.did`의 기존 1.0.0 계약은 pinned Recipe용으로 보존합니다. 그 design-object schema는 호환용이며 새 작성 API가 아닙니다. 새 호출자는 `stats.binary_regression`·`stats.linear_dml`·`stats.two_period_contrast`를 사용합니다. 기존 Run·버전을 다시 쓰거나 자동 alias하지 않습니다.

## Python·pytest·notebook

같은 계산을 Python·pytest에서 사용하고, 선택적 notebook에서 작성·등록·직접 인자·표 결과를 확인합니다. 로컬 계산은 디버깅을 위해 현재 프로세스에서 실행합니다. 서버는 provider credentials 없는 기존 제한된 자식 프로세스에서 계산하며 임의 코드 sandbox는 아닙니다. [직접 시나리오](method-scenarios.md)를 참고하세요.
