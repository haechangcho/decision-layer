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

## 현재 Method 목록

통계 분석은 선택 기능입니다. `stats.binary_regression`, `stats.linear_dml`, `stats.two_period_contrast`는 필요할 때 검토한 Python 등록 코드로 활성화합니다. 이전 `stats.adjusted_difference`, `stats.dml`, `stats.did`는 웹, REST, MCP 목록과 후보 탐색에서 제외합니다. 기존 고정 Recipe를 위해 명시적인 조회와 실행은 원래 1.0.0 계약으로 유지합니다. 자동으로 이름을 바꾸거나 과거 Run을 수정하지 않습니다. OLS, 회귀 조정, DML, CEM은 서로 다른 분석 방법이므로 유지합니다.

`causal.cem`도 기본 목록과 AI 탐색에서 제외합니다. 기존의 명시적인 참조는 1.1.1 호환 실행을 유지합니다.

## MVP DoWhy 매칭과 OLS 회귀 조정

기본 목록에 두 가지 작은 Method를 제공합니다. 둘 다 `outcome`, `treatment`,
`confounders`, `unit`과 공통 실행 조건 `scope`를 받습니다.

| Method | 직접 호출하는 추정기 | 비교 대상 |
| --- | --- | --- |
| `stats.binary_matching` | `backdoor.distance_matching` | ATT: 처치 집단의 1 대 0 비교 |
| `stats.regression_adjustment` | `backdoor.linear_regression` | 저장된 처치 1단위 증가당 변화량 또는 특정 대비 |

두 방법의 대상 모집단은 다릅니다. 여기서 OLS는 이진 처치의 차이를 교란변수로
조정합니다. 선택 기능인 `stats.ols`는 일반적인 연관성 회귀 계수를 반환합니다.
가정한 그래프 아래의 식별이나 placebo 검사가 인과성을 증명하지는 않습니다.
[공식 추정기 문서](https://www.pywhy.org/dowhy/v0.14/dowhy.causal_estimators.html)를 참고하세요.
구현과 실행 실험은 0.13을 유지합니다.

`.[stats,dowhy]`를 설치한 뒤 알려진 효과를 가진 예제를 실행합니다.

```bash
.venv/bin/python -m examples.methods.patterns.dowhy_basics
.venv/bin/python -m pytest tests/unit/test_dowhy_matching.py
```

실제 서비스와 같은 등록 Method와 entity 조회를 사용합니다. 합성 개체 200개의
처치 전 변수 분포는 두 집단에서 같고, 결과는 `3*x + 2*treatment`입니다.
두 추정값은 모두 2.0입니다. Journey 데이터의 실제 인과효과를 뜻하지 않습니다.

연결된 session에서는 기존 semantic 참조를 넣습니다.

```python
trial = await session.run(
    "stats.binary_matching",  # Or stats.binary_regression
    outcome=outcome_ref,
    treatment=treatment_ref,
    confounders=[baseline_ref],
    unit=unit_ref,
    scope=scope,
)
```

이 호출 코드는 builtin이 등록된 연결 session과 확인한 참조를 전제로 합니다.
실행 예제는 이 값들을 준비합니다. 매칭의 처치는 0/1이어야 합니다. 회귀는 연속형 숫자도 지원합니다. 개체마다 완전한 관측
하나가 있어야 하고 집단마다 최소 30개가 필요합니다. 교란변수는 처치 전에 측정해야
합니다. 결과 측정 시점, 미관측 교란의 부재, 개체 독립성, 간섭 부재에는 도메인 근거가
필요합니다. Method가 참조 경로에서 이런 사실을 추측하지 않습니다.

매칭은 인코딩한 교란변수를 표준화하고 가장 가까운 비교 개체 한 개를 복원 추출합니다.
적합한 처치 확률이 [0.05,0.95] 밖이거나, 서로 다른 매칭 비교 개체가 30개 미만이거나,
거리가 1.0을 넘거나, 매칭 후 표준화 평균 차이의 절댓값이 하나라도 0.1을 넘으면
거절합니다. 보수적인 Method 운영 기준이며 통계적 증명이 아닙니다. 범주형 변수만
있거나 동률이 많은 데이터는 비교 개체 수 기준을 충족하지 못할 수 있습니다.
처치 집단을 조용히 제외해 ATT의 모집단을 바꾸지 않습니다. 재사용 수, 거리,
인코딩, 매칭 전후 균형을 기록합니다. 결측, 중복 개체, 비이진 처치, 작은 집단,
관측된 지원 범위 부족은 거절합니다. 재사용 개체에 대한 매칭 신뢰구간이나 유의성은
제공하지 않습니다. 가정은 미검증, 인과효과는 미확립으로 표시합니다. 다른 기준이나
대비를 지원하려면 자유 설정 대신 검토한 새 버전이 필요합니다.

Complete Journey의 Docker API는 기본적으로 stats와 dowhy 의존성을 포함해 빌드합니다.
다른 설치에서는 의존성을 명시적으로 설치합니다. 분석 요청 중 자동 설치하지 않습니다.
핵심 의존성만 설치한 환경에서도 일반 조회 Method는 사용할 수 있습니다.

## 연속형 처치는 변수만 넣어 실행하기

기본 OLS Method는 `stats.regression_adjustment`입니다. 이전
`stats.binary_regression`은 원래 계약으로 명시적인 호환 실행을 유지합니다.

```python
trial = await session.run(
    "stats.regression_adjustment",
    outcome=purchase_amount,
    treatment=discount_rate,
    confounders=[baseline_amount],
    unit=customer,
    scope=scope,
)
```

위 연결 session과 참조는 호출자가 준비합니다. 기본 결과는 저장된 처치 1단위
증가당 조정된 기울기입니다. 할인율이 0에서 1 단위로 저장됐다면 기울기 50은
1%p당 0.5에 해당합니다. 같은 데이터를 0에서 100으로 저장하면 기울기는 0.5입니다.
Method는 단위를 임의로 변환하지 않습니다.

특정 대비가 필요할 때만 `control_value=0.10`, `treatment_value=0.20`을 모두
추가합니다. 예제의 결과는 5입니다. 지정한 값은 관측 범위 안에 있어야 합니다.
범위 확인이 교란변수별 관측 지원을 증명하지는 않습니다. 연속형은 개체 60개 이상과
서로 다른 값 10개 이상, 이진 처치는 집단마다 30개 이상이 필요합니다. 결측, 중복,
숫자가 아닌 범주, 상수 처치, 비유한 값, rank 부족, 한쪽 대비 값 누락, 지원하지 않는
범위 밖 대비는 거절합니다.

기본 결과는 일정한 선형 기울기이며, 관측 범위를 벗어난 실제 +1 개입의 효과를
증명하지 않습니다. 상세 결과에 `result_scale`, `slope`, `contrast`,
`estimation_contrast`, 처치 참조와 지원 범위를 기록합니다. 시간 순서와 식별 가정은
미검증이며 신뢰구간은 제공하지 않습니다. 매칭은 계속 이진 처치 집단을 대상으로 합니다.

한영 실습 노트북과 같은 구현을 실행합니다.

```bash
.venv/bin/python -m examples.methods.patterns.continuous_regression
.venv/bin/python -m pytest tests/unit/test_regression_adjustment.py
```
