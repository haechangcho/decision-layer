# CEM과 PyWhy: 실행 실험에 기반한 재검토

검토일: 2026-10-12. **권고는 CEM의 일부 기능 분리와 기존 버전 유지다. DoWhy로 전면 통일하지 않는다.** 아래 `review.*`는 실행 검증한 로컬 실험 Method이며 production builtin이 아니다. 기존 CEM·Recipe·Run·의존성 pin은 변경하지 않았다. 향후 설계와 실제 구현을 구분한다.

## 1. 진단과 권고

현재 `cem.py`와 `matching.py`는 단순 estimator보다 많은 일을 한다. 특히 provider 집계만으로 계산하는 경로는 entity 행 전체를 가져와야 하는 PyWhy estimator와 비용·권한 요구가 다르다. CEM의 교체 비용은 매칭 함수의 줄 수로 판단할 수 없다.

| 현재 책임 | 현재 동작과 문제 | 권고 |
| --- | --- | --- |
| 대상·비교 집단 | dimension 값·제외·수치 범위, 상호 배타성 검사 | 기존 semantic 조건·scope를 재사용. 처치 대비와 분석 모집단은 별도로 명시 |
| 교란변수 구간화·매칭 | quantile/명시 구간과 범주 strata; 공통 strata 선택 | CEM 고유 알고리즘으로 유지. distance matching/DML로 같은 의미의 대체 불가 |
| 선택·가중치 | 공통 strata 안에서 target 빈도로 양쪽 평균 가중 | 작은 순수 계산 함수 유지. 탈락 수·유지율·가중치·분석 모집단을 결과에 기록 |
| 균형 | 구간화 strata 분포의 불균형; 조정 후 0은 구조적 결과 | 원래 변수의 SMD·분포·지원 범위 진단을 추가 제안. 원자료가 없으면 검사 불가라고 표시 |
| 결과·효과 | raw/adjusted 차이; 검증된 proportion에 제한된 구간 | matched comparison과 causal claim 분리. 회귀/DML은 다른 Method로 제공 |
| 검증·provenance | 의미·count/분모·추출 제한·품질·query 근거 | Decision Layer에 유지. DoWhy가 provider 권한·grain을 대신 검증하지 않음 |

현재 native-average 경로는 명시적인 count, 공통 provider 단위, unit별 유한 outcome 등을 요구한다. measure를 처치로 사용하는 경로의 unit 평균은 provider의 원래 분모와 달라질 수 있다. 이 보호 장치를 없애면 오히려 잘못된 답이 쉬워진다.

현재 CEM의 차이는 `Σ n_target,s × (mean_target,s − mean_comparison,s) / Σ n_target,s`이다. 합은 **유지된 공통 strata**에 한정된다. 전체 모집단 ATE나 원래 모든 처치자의 ATT와 자동으로 같지 않다. 구간 안에 잔여 교란이 있으면 매칭만으로 인과 해석도 성립하지 않는다. 현재 `causal_conditional` 표시는 새 통계 Method의 `associational`보다 강하다. 과거 결과를 소급 재해석하지 말고 새 계약에서 표현을 교정해야 한다.

권고: CEM 1.1.1은 호환성과 집계 기반 비교 용도로 유지하고 인과 분석의 기본 선택에서는 제외한다. 새 계약에서는 명확한 `matched_comparison`과 분석별 효과 추정을 분리한다. 일반 OLS는 statsmodels, 검토된 효과 추정은 DoWhy native 또는 EconML 직접 호출을 사용한다. 범용 estimator plugin runtime은 만들지 않는다.

## 2. 처치 유형보다 분석 질문을 먼저 정한다

| 질문 | 명시할 입력 | 후보·지원 경계 |
| --- | --- | --- |
| 이진 처치 | 0→1, 목표 모집단, ATE 또는 ATT | matching·회귀 조정·DML 중 가정과 진단에 맞게 선택 |
| 다중 범주 | 전체 범주 순서, 인코딩 기준, 실제 비교 쌍 | 예: 기준 control, 비교 basic→plus. 범주형 DML 실험 완료 |
| 연속형 | 단위와 0.5→1.5 같은 실제 대비 | 연속형 DML 실험 완료. LinearDML의 처치에 대한 선형 반응 가정을 명시 |
| 연속 처치의 구간 비교 | 경계·포함 규칙·구간 내 처치의 의미 | 새로운 분석 질문. 원래 연속 처치의 고정 용량 효과와 다름. 일반 지원은 보류 |
| 처치 없는 회귀 | outcome·features·unit | OLS 연관성 계수. 가짜 treatment/DAG를 만들 필요 없음 |

처치의 구간화는 질문과 estimand를 바꾼다. 예를 들어 할인율 0–10% 대 10–20%는 할인율 5%→15%의 효과와 같지 않다. 각 구간의 여러 용량을 어떤 개입으로 정의하는지 없으면 일관성 가정도 모호하다. 정보 손실·경계 민감도·구간 내 분포 차이를 보고해야 한다. 재사용할 업무상 구간 정의는 semantic layer가 소유하고, 분석자가 선택한 실험적 구간은 분석 설정과 provenance에 남긴다.

반면 CEM에서 **교란변수**인 사전 구매액을 구간화하는 것은 처치를 재정의하지 않고 조정 해상도를 바꾼다. 더 거친 구간은 표본을 더 남길 수 있지만 잔여 불균형도 남긴다. 결과를 본 뒤 유리한 경계를 고르지 않는다.

ATE는 선택한 목표 모집단의 평균 대비, ATT는 명시한 처치를 실제 받은 집단에서의 평균 대비, CATE는 사전 effect modifier X 조건에서의 대비다. 다중 범주 ATT라면 “plus 집단에서 plus 대 basic”처럼 대상 집단까지 지정한다. CATE 예측의 평균을 누구에 대해 내는지가 ATE/ATT를 결정한다. unit key만으로 독립성은 증명되지 않는다.

## 3. 서로 다른 방법을 구분한다

| 방법 | 표본·추정 대상 | 추가 가정·부담 |
| --- | --- | --- |
| 현재 CEM | 공통 구간의 유지된 target 분포; unmatched 탈락 | 구간화·잔여 교란·표본 변경. 집계 pushdown 가능 |
| DoWhy distance matching | 최근접 control/treated로 ATT·ATC·ATE | 이진 처치 한정. 거리 척도·스케일·희소 strata·재사용을 점검. 소스에 caliper 미구현 TODO가 있어 먼 이웃도 매칭될 수 있음 |
| 회귀 조정 | 조정 모형의 대비를 목표 표본에 평균 | 함수 형태·상호작용·외삽에 민감. 공통 strata 선택과 다름 |
| LinearDML | nuisance를 cross-fit하고 X에 대한 선형 효과 모형 적합 | 충분한 fold별 표본, 처치 잔차 변동, overlap, nuisance 품질. 교차 적합이 미측정 교란을 제거하지 않음 |

효과 해석에는 공통적으로 식별 가정이 필요하다. 고급 알고리즘으로 바꾸는 것 자체가 그 가정을 강화하지 않는다. [DistanceMatchingEstimator 공식 소스](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/distance_matching_estimator.html), [LinearDML 공식 계약](https://www.pywhy.org/EconML/_autosummary/econml.dml.LinearDML.html).

## 4. 세 가지 호출 경로의 실제 차이

1. **DoWhy native:** DAG와 식별식 → 검토된 matching/회귀 → 선택적 refutation. 식별은 입력한 DAG가 참이라는 조건 아래의 계산이다. 현재 실험은 모든 W가 T와 Y의 사전 공통 원인이라는 명시적 템플릿이다.
2. **DoWhy → EconML:** 같은 식별 근거를 유지하고 wrapper가 Y/T/X/W를 매핑한다. 작동하지만 wrapper의 대상 집단·effect modifier 전달 계약도 검증해야 한다.
3. **EconML 직접:** Y/T/W/X, 대비와 평가 표본을 명시하기 쉽다. DML 작성의 우선 경로로 권고한다. Decision Layer가 식별 가정·근거·진단을 보존해야 하며, 직접 호출에 자동 식별 기능이 생기는 것은 아니다.

두 버전에서 `backdoor.econml.dml.LinearDML` 문자열 경로는 실행됐지만 deprecated 경고가 발생했다. 인스턴스를 받는 `backdoor.econml` 경로로의 전환은 별도 회귀 테스트 후 한다. 단지 `discrete_treatment=True`만 주는 예시는 불충분하다. 실험 코드는 범주 순서, 분류/회귀 처치 모형, outcome 모형, seed, 3-fold 분할, X/W, 실제 T0/T1, `inference=None`을 명시한다.

**실제로 발견한 함정:** 이질적 효과 실험에서 wrapper에 `target_units="att"`를 주면 0.13/0.14 모두 ATE 1.973을 반환했다. 실제 ATT는 2.564이고 직접 호출은 2.559였다. `effect_modifiers=["x"]`를 `estimate_effect`에도 명시하고 target callable로 표본을 선택했을 때 2.559로 일치했다. 0.13에서는 constructor에만 X를 주면 추정 시 그래프에서 modifier를 다시 찾아 이 사례의 X가 빠졌다. 따라서 문자열 이름이 보장하는 것처럼 UI에 ATT를 표시하면 안 된다. [wrapper 소스](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/econml.html), [CausalModel 소스](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_model.html).

아래는 실행 검증한 함수다. 실험용으로 한정된 입력이며 arbitrary estimator 선택 API가 아니다.

<<< @/../examples/methods/pywhy_review/experiment.py#dowhy_native

<<< @/../examples/methods/pywhy_review/experiment.py#dml_routes

DoWhy LinearRegressionEstimator는 실제로 statsmodels OLS를 사용한다. 같은 Y/T/W와 선형 모형에서는 일반 OLS의 처치 계수와 같은 숫자가 나왔다. 차이는 숫자의 브랜드가 아니라 식별 질문·DAG·대비·해석이다. 일반 OLS를 전부 DoWhy로 감싸는 실익은 작다. [공식 구현](https://www.pywhy.org/dowhy/v0.14/_modules/dowhy/causal_estimators/linear_regression_estimator.html).

## 5. 설치하고 같은 구현을 실행한다

저장소 루트에서 Python 3.11 환경을 사용한다. 아래 constraints는 검토 환경의 전이 의존성 snapshot이다. 모든 OS/Python 조합의 지원 보증은 아니다. notebook 제품이나 웹 코드 편집기는 필요하지 않다.

```bash
python3.11 -m venv .venv-pywhy-review
.venv-pywhy-review/bin/python -m pip install -e '.[dev,stats,dowhy,econml]' -c examples/methods/pywhy_review/constraints-013-py311.txt
.venv-pywhy-review/bin/python -m examples.methods.pywhy_review.experiment
.venv-pywhy-review/bin/python -m examples.methods.pywhy_review.session
.venv-pywhy-review/bin/python -m pytest -q examples/methods/pywhy_review/test_review.py
```

실행 소스는 `examples/methods/pywhy_review/`에 있다. `experiment.py`는 일반 Python 함수, `methods.py`는 typed adapter, `session.py`는 독립적인 query fixture를 통한 등록·실행, `test_review.py`는 같은 구현을 검사한다. `explore.ipynb`도 이 함수를 import한다. notebook 셀은 pytest에서 실행했다. 별도 Jupyter 설치·kernel 선택은 선택 사항이며 notebook UI 자체를 테스트한 것은 아니다.

```python
from examples.methods.pywhy_review.experiment import data, native, dml

matching = native(data(), "matching", "att")
regression = native(data(), "linear", "ate")
category = dml(data("categorical"), "categorical", control="basic", treated="plus")
dose = dml(data("continuous"), "continuous", control=0.5, treated=1.5)
# In an async function or Jupyter cell:
from examples.methods.pywhy_review.session import run_case
trial = await run_case("categorical")
print(trial.queries, trial.result.primary.data)
```

breakpoint는 `calculate`/`dml`에 둔다. query와 시도 기록은 `trial.queries`/`trial.attempts`에서 검사한다. notebook에 구현을 복사하지 않는다.

## 6. Semantic 입력은 그대로 유지한다

Cube 연결·객체 탐색·기간·필터 입력은 [첫 Method](./methods)의 실행 API를 그대로 쓴다. measure는 Y, treatment는 T, confounders는 W, effect modifiers는 X, entity는 unit으로 내부 매핑한다. 같은 객체가 W와 X에 모두 필요할 수도 있다. Outcome은 선택한 unit에서 의미가 있는 provider 정의여야 하며 aggregate ratio를 아무 설명 없이 unit outcome으로 바꾸지 않는다.

아래 실험용 Method는 실제 등록·실행했다. 단일 수치 confounder, 고정된 세 범주 또는 두 W strata의 연속 처치 실험으로 제한했다. 일반적인 업무 데이터 지원을 뜻하지 않는다.

<<< @/../examples/methods/pywhy_review/methods.py#typed_methods

`session.py`는 `measures={"outcome": Y}`, `dimensions={"treatment": T, "confounder": W}`, `entity=UNIT`, `Scope(PERIOD, DATE)`, eligible filter와 대비 params로 실행한다. 별도 작성한 DatasetSpec이 기간·필터·entity·열·행 제한과 일치해야 테스트가 통과한다. 선언 함수는 기존 canonical manifest/spec으로 컴파일되며 backend 클래스 경로를 REST/MCP 입력으로 받지 않는다.

**다음은 제안이며 아직 구현되지 않은 확장 API다.** 큰 estimator 설정 객체 대신 검토한 Method별 짧은 typed signature를 사용한다.

```python
# DESIGN PROPOSAL ONLY — not an available registered Method.
async def reviewed_dml(ctx, *, outcome: Measure, treatment: Dimension | Measure,
                       confounders: list[Dimension | Measure],
                       effect_modifiers: list[Dimension | Measure], unit: Entity,
                       categories: list[str], control: str, treated: str,
                       target: Literal["ate", "att"]) -> Estimate:
    ...
```

실제 구현에서는 범주형·연속형의 대비 인자 타입을 분리하고, target population을 scope와 별도 평가 집단으로 기록한다. CATE는 X별 결과와 평균 대상 표본을 구분하며 임의 X 외삽은 거절한다. 사용자가 처치 타입을 고르면 알고리즘을 자동 선택하지 않는다.

개발자가 쓸 것은 typed 함수, 의미 역할, 짧은 계산 helper다. 내부 계약에는 canonical spec, provider 권한·grain 검증, bounded extraction, server compute 제한, alias→semantic ref, 인코딩·대비·fold·표본 선택·가정·실제 package 버전·query 근거가 남는다. 로컬 직접 실행과 server 격리 실행의 제한은 다르다. 이번 새 adapter의 검증은 로컬 canonical session까지이며 웹/REST/MCP 배포를 했다는 뜻은 아니다.

Method는 하나의 분석 절차다. 여러 query로 표본과 비교를 조합해도 한 추정 절차라면 Method 안에서 작성한다. 어떤 집단을 먼저 조사하고 어떤 분석을 이어 할지는 Recipe다. 모든 인터페이스가 등록된 같은 계약을 실행하며 인터페이스마다 추정 코드를 복제하지 않는다.

## 7. 정상 결과와 실패를 직접 확인한다

n=4,000, seed=17의 독립 단위 합성 데이터. 아래 값은 두 환경 모두 표시 자릿수에서 같았다. 저장된 `results-0.13.json`, `results-0.14.json`에 실제 버전과 경고가 있다. 신뢰구간·p-value는 계산하지 않았다.

| 사례 | 알려진 값 | 실행 결과 |
| --- | --- | --- |
| 이진 matching ATT | 2 | 2.00550 |
| DoWhy 회귀 / 동일 일반 OLS 계수 | 2 | 2.00293 |
| 직접/wrapper 이진 DML | 2 | 1.99942 |
| basic→plus DML | 3 | 3.00689 |
| 0.5→1.5 연속 DML | 2 | 1.99854 |
| 이질적 효과 ATE / ATT | 1.974 / 2.56369 | 1.97309 / 2.55912 |
| 두 구간 CEM 계산 kernel | 2 | 2.24305 |

CEM은 표본 100%를 유지하고 구간화 불균형은 0이었다. 그러나 원래 W 평균 차이 0.08182가 남았다. 이는 의도적으로 거친 구간을 쓴 반례이며 CEM의 모든 설정이나 provider 실행 경로를 비교한 benchmark가 아니다. placebo 평균은 −0.00992였으나 통과/인과성 판정으로 사용하지 않았다.

pytest는 위 수치와 wrapper ATT 함정을 검증한다. 실패 시나리오는 지원하지 않는 처치 유형, unit 중복, 결측, 무한값, 한 처치군만 존재, 작은 처치군, propensity support 실패, 같은 대비 값, 알 수 없는 범주, 관측 범위 밖 용량, 상수 용량이다. 동일한 대비 값은 query 전에 거절하며 모든 실험 추정치는 가정 미검증·연관성 결과로 기록한다. 기본 환경에서는 선택적 라이브러리가 없으면 이 실험 테스트를 skip한다.

검증 결과: notebook 셀 실행을 포함해 환경별 실험 테스트 16개가 통과했다. 기존 Method·문서 회귀 테스트 58개와 VitePress 빌드도 통과했다. 경고는 숨기지 않고 기록했다.

## 8. 검사할 수 있는 것과 가정해야 하는 것

**현재 실험의 자동 검사:** key 유일성·결측·유한값·범주·군별 최소 30개·적합 logistic 확률 0.02–0.98·연속형의 W strata별 관측 min/max. 이 숫자는 실험 정책이며 통계적 충분조건이 아니다. 같은 데이터에 threshold를 맞춰 결과를 통과시키지 않는다.

**production 승격 전 필요한 검사:** 열 rank·처치 잔차 변동·fold별 범주와 표본·nuisance 적합 진단·카테고리 인코딩 일관성·거리 스케일·연속 지원 밀도·효과 수정 변수의 지원 범위. 표본 구조가 반복 관측/cluster면 현재 iid template을 거절한다. 데이터의 타임스탬프/구간 메타데이터가 있으면 covariate < treatment < outcome을 검사하고, 없으면 자동 검증했다고 쓰지 않는다. 새 작성 API에서는 가정 체크박스를 제거했다. 식별 근거는 별도로 검토해야 한다.

**사용자가 근거와 함께 명시할 가정:** 미측정 교란 없음, 일관된 처치 정의, 간섭 없음, 선택/누락 과정의 타당성, 선후 관계와 모델 가정. 라이브러리의 식별 성공은 DAG의 진실성을 검증하지 않는다. 미확인 상태면 causal-labelled 실행을 거절하거나 명시적인 associational 실험으로 제한한다.

Refutation은 선택한 교란/모형 실패를 탐색하는 진단이지 인과성 증명이 아니다. 신뢰구간은 estimator의 추론 방식과 독립·cluster·시계열 표본 구조가 맞을 때만 지원한다. matching 이웃 재사용이나 표본 선택을 무시한 일반 bootstrap/OLS 구간을 붙이지 않는다.

## 9. Complete Journey로 확인할 수 있는 범위

현재 sample은 dunnhumby Complete Journey를 PostgreSQL/Cube로 제공한다. 데이터의 출처가 Databricks 관련이어도 현재 connector를 Databricks로 테스트했다는 의미는 아니다.

충분한 범위: 연결·catalog·권한 경로·기간/집단 필터·entity grain·추출 제한·결측/중복·실행 근거, descriptive/OLS/window 차이의 SQL 대조, 지원이 부족할 때의 거절. 기존 journey 시나리오를 재사용한다.

불충분한 범위: 알려진 인과효과, 무작위 배정, 실제 캠페인 수신 시각, 모든 unit의 관측 완전성, 평행 추세, 미측정 교란 부재. campaign-household는 비무작위 대상 선정과 겹치는 캠페인, 고정 pre/post 30일 창을 가진다. 여러 campaign의 같은 household를 iid로 취급하면 안 된다. 기존 표본에서 명시적 가정을 넣어도 support 진단이 거절한 사례가 있으므로 이를 해결하려고 threshold를 임의 완화하지 않는다.

이 검토에서는 Complete Journey를 새로 재실행하지 않았다. 데이터/시나리오 코드와 기존 검증 근거를 확인했고, 신규 숫자 검증은 합성 데이터로 했다. 다음 단계는 비선형·비중첩·누락 교란·효과 이질성·cluster·여러 seed의 합성 회귀 suite다. 단일 성공 DGP로 범용 정확성을 홍보하지 않는다.

## 10. 0.13과 0.14, 의존성 비용

| 항목 | 현 지원 환경 | 별도 upgrade 실험 |
| --- | --- | --- |
| DoWhy | 0.13 | 0.14 |
| EconML | 0.16.0 | 0.16.0 |
| NumPy | 1.26.4 | 2.2.6 |
| pandas / SciPy / sklearn | 2.3.3 / 1.15.3 / 1.6.1 | 동일 |
| statsmodels / Python | 0.15.0 / 3.11.14 | 동일 |
| 신규 실험 | 수치·거절·typed adapter·notebook 셀 | 같은 테스트 |

DoWhy 0.14의 배포 metadata는 NumPy >2.0을 요구한다. 프로젝트의 현재 extras/builtin NumPy <2와 충돌하므로 버전 문자열만 바꾸면 안 된다. DoWhy 0.13 자체가 Python 3.11에서 NumPy <2를 강제하는 것은 아니다. EconML 0.16은 sklearn <1.7과 SHAP 제약도 가진다. [0.14 배포 metadata](https://pypi.org/pypi/dowhy/0.14/json), [0.14 릴리스](https://github.com/py-why/dowhy/releases/tag/v0.14).

```bash
python3.11 -m venv .venv-pywhy-014
.venv-pywhy-014/bin/python -m pip install -e '.[dev,stats]' 'dowhy==0.14' 'econml==0.16.0' -c examples/methods/pywhy_review/constraints-014-py311.txt
.venv-pywhy-014/bin/python -m examples.methods.pywhy_review.experiment
.venv-pywhy-014/bin/python -m pytest -q examples/methods/pywhy_review/test_review.py
```

0.14는 별도 환경에서 수치 실험이 통과했지만 NumPy 행렬 연산의 overflow/invalid/divide-by-zero 경고도 기록됐다. 반환값이 유한하고 기대값에 가까운 것만으로 이 경고를 무시해 production 지원을 선언하지 않는다. 원인·플랫폼 재현을 조사하고 경고 처리 정책을 정하는 upgrade gate로 남긴다. 0.13의 pandas 위치 indexing 경고와 두 버전의 문자열 wrapper deprecation도 기록했다.

runtime은 의존성을 설치하지 않는다. contributor는 검토된 optional extra/constraints를 한 번 설치하고, 배포는 정해진 환경을 사용한다. core 사용자에게 causal stack을 강제하지 않는다. upgrade는 NumPy/compiled dependency 호환성, API 전달 계약, 수치·실패·추론 회귀, lock 갱신 비용을 함께 가진다.

## 11. 구현·마이그레이션·문서 계획

다음은 권고 계획이며 production 전환 완료를 의미하지 않는다.

1. **해석 계약:** matched comparison/association/conditional causal를 명확히 하고 estimand·대비·목표/실제 표본·확인되지 않은 가정 필드를 정한다. 기존 CEM은 수정하지 않고 새 Method ID 또는 version 계약으로 교정한다.
2. **작은 공통 검사:** unit·인코딩·명시 대비·지원·표본 선택 기록을 실제 중복된 부분만 분리한다. estimator별 모델 조건은 해당 helper에 남긴다. 모형 자동 선택이나 범용 kwargs는 금지한다.
3. **검토된 estimator 승격:** native binary matching/회귀, 직접 categorical/continuous DML 순서로 실제 source와 실패 계약을 통과시킨다. CATE·ATT는 평가 표본과 modifier 누락 회귀 테스트가 필수다. CI는 별도 검토 전 미지원이다.
4. **기존 호환성:** CEM 1.1.1과 과거 Run artifact는 보존하고 자동 재계산/재라벨링하지 않는다. 현재 registry는 이름별 한 구현이므로 같은 ID에 두 version을 등록해 공존한다고 가정하면 안 된다. 다른 ID로 병행하거나 version resolution을 먼저 구현한다. Recipe pin을 자동 alias하지 말고 복제→명시적 opt-in→shadow 비교→새 pin 순서로 전환한다. 제거는 사용 현황·대체 능력·보존/재실행 정책을 확인한 별도 결정이다.
5. **인터페이스 검증:** 같은 canonical spec을 Python/REST/MCP/Web으로 실행해 같은 버전·대비·query·거절 상태인지 검사한다. 이번 local adapter 테스트를 그 검증으로 대체하지 않는다. 실행 제한과 서버 compute 중단도 회귀 검증한다.
6. **문서:** 첫 연결→객체 선택→단일 query→여러 query→entity 역할→Python 실험→pytest 실패→선택 notebook→등록/공유 순서로 VitePress를 구성한다. 한·영은 같은 코드 include와 사례 ID를 사용한다. 현재 페이지와 기존 작성/시나리오 가이드는 이 순서를 연결하고, 지원 표와 거절 사유를 API reference와 함께 갱신한다.

## 12. 제품 표현

현재 권장 문구: **“Governed semantic data 위에서 검토된 DoWhy·EconML 기반 분석 Method를 실행하고, 가정·검증·실행 근거를 함께 확인할 수 있습니다.”**

“PyWhy 친화적”은 일반 Python 연동과 제한된 테스트 범위를 함께 명시할 때 적절하다. “모든 PyWhy estimator 지원”, “자동 인과추론”, “refutation으로 인과효과 검증”은 현재 근거를 넘는다. 다중 범주/연속 처치는 아직 이 페이지의 실험이며 기본 제품 지원이라고 쓰지 않는다. PyWhy의 공식 인증이나 제휴를 암시하지 않는다.
