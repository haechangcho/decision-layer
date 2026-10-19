# Write and test a Method

Start with a [Method project](method-projects.md): one visible directory holds Python
calculations and Skill Markdown. CLI checks, local Python and API startup read the
same files. The complete example is in `examples/methods/project`.

```sh
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer new skill metric_review
decision-layer check
decision-layer list
decision-layer serve --reload
```

Each `<name>/methods/<definition>/method.py` exports one `METHOD` object created
with `python_method`. Each Skill uses `SKILL.md` in its own definition folder.
`list` prints the source path so registration can be traced to its definition.
The project marker is `decision-layer.yaml`; deployment can point `DL_PROJECT_DIR`
at this directory. Existing module-based `METHODS` registrations remain compatible.

Use an ordinary function for new calculations, a Skill to guide recorded queries,
and a Recipe for a reusable sequence of existing Methods. Declare inputs with
`DataInput(columns={...})` with explicit `Column(source="measure")` or
`Column(source=["measure", "dimension"], dtype="number", multiple=True)` declarations.
Matching function arguments receive resolved column names automatically. Use
`Column(source="dimension", role="entity_key")` for the observation key; choose
its name, such as entity_id, and select the reference using
`session.run(..., bindings={"entity_id": "cube://...", ...})`. Every semantic
input uses the same name at registration and execution. Legacy measures/dimensions, RoleSpec and column_args declarations remain valid.

For a notebook walkthrough open
`docs/tutorials/methods/write_your_method.en.ipynb`. It covers ordinary Python,
local registration and OLS with prepared data. Continue with the
[project guide](method-projects.md) for server and Web/MCP usage. Local trials use the canonical Registry
but do not upload code or create stored Runs. Server execution uses the same
contracts and records evidence in a Run.

## Advanced path: when source queries need direct control

The following source-aware examples are optional; ordinary calculations do not require them.

## 1. Start without a live connection

Run from the repository root. This first test needs Python 3.11+ and core dependencies; cases requiring statistical libraries are skipped.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m examples.methods.scenarios --case by_group
.venv/bin/python -m pytest -q tests/examples/test_scenarios.py
```

## 2. Write the function

`Measure` and `Dimension` receive references to existing semantic objects. `ctx` applies periods, filters, permissions and limits. The signature generates the manifest, avoiding duplicate role declarations and argument mapping. This is the tested source.

<<< @/../examples/methods/scenarios/methods.py#group_metric

`@method` names the Method and records its version. Omitting `interpretation` defaults to `association`, which means observational summaries and relationships: grouped queries, monthly trends
and regression associations. It does not claim a causal effect. New Methods use
this one category; the old `descriptive` and `associational` values remain supported.

`Table.from_dataset(data)` returns rows and preserves their semantic column information.
Monthly queries use the same `Table` return type. The web uses the time information
to display a trend; you do not need a separate return type.

<<< @/../examples/methods/scenarios/methods.py#series

Use `Estimate` when the main result is one estimated value with analysis details.

### How AI requests and Python calls supply inputs

Example request: “Show the top 3 departments by sales amount for store 364 in February 2001.”

The AI finds the sales-amount measure and department dimension in the semantic layer and fills these inputs:

- `metric`: path to the model and its sales-amount measure
- `group`: path to the model and its department dimension
- `limit`: the requested 3; uses the function default when omitted
- `scope`: February 2001, date basis and the store 364 filter

For example, `cube://journey/transaction/receipts` names:

- `cube://`: the Cube semantic provider
- `journey`: the configured Cube instance
- `transaction`: the Cube model
- `receipts`: a measure defined in that model

Once connected to Cube, find this path in the catalog and pass it to `run(metric=...)`. It is not a database table or SQL column path. You can also pass `cube://journey/product/department` from another model as `group`; Cube decides whether the models can be joined and how. In the practice path `cube://practice/observations/value`, `practice` names the practice connection and `observations` and `value` are names in the practice catalog.

In Python, pass `metric`, `group`, `limit` and `scope` directly to `run(...)`. At execution time:

- The value passed to `run(metric=...)` reaches the Method function as `metric`. `group` and `limit` work the same way.
- The period and filters in `scope` become part of `ctx`. `ctx.aggregate(...)` applies them to the query.
- The session's data connection, permissions and execution limits are used by `ctx` when it queries.

Missing or ambiguous inputs are handled as follows:

- If the requested metric or period is unclear, the AI asks the user.
- If the runtime returns `needs_input`, the AI relays its question.
- Missing required Method arguments cause an input error.

The Method uses `ctx.aggregate(...)` to query with the resolved period, filters, permissions and limits.

Python calls execute directly and do not conduct a conversation. The AI uses the registered Method's declared inputs when preparing MCP calls. It sends the analysis scope when creating the Run and Method arguments in its execution step; both reach the same execution context and registry. A required annotation declares a required input, not an automatically generated chat question. A Method may raise `NeedsInput` for an analytical choice it cannot resolve; the caller must obtain the answer and retry with valid inputs. Defaults are used only when supported by the Method or Recipe. Connection credentials and permission rules come from the configured execution environment.


## 3. Register, execute and verify

Run this in a notebook cell or an async function. `FixtureProvider` compares the entire request with an independently written `DatasetSpec`; it does not copy the Method request as its oracle. Incorrect query conditions fail even when numbers look right.

```python
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope
from examples.methods.scenarios.methods import group_metric
from examples.methods.scenarios.scenarios import scenarios, M, GROUP, DATE, FEB

scenario = next(s for s in scenarios() if s.name == "by_group")
provider = scenario.provider()
session = await MethodSession.fixture(provider)
session.register(group_metric)
trial = await session.run(
    group_metric,
    metric=M, group=GROUP,
    scope=Scope(FEB, DATE), limit=3,
)
assert [r["metric"] for r in trial.result.primary.data] == [30, 20, 10]
provider.assert_consumed()
print(trial.queries)
print([(a.label, a.status) for a in trial.attempts])
session.close()
```

## 4. Connect a real semantic source

```python
import os
from decision_layer.dev import MethodSession
from decision_layer.methods import Scope, Filter
from decision_layer.semantic.credentials import RequestCredentials

session = await MethodSession.cube(
    os.environ["CUBE_API_URL"], RequestCredentials(os.environ["CUBE_TOKEN"]),
    instance="journey",
)
metrics = session.catalog.search(kind="measure", text="sales")
metric = metrics[0].ref  # Inspect titles/definitions before choosing.
print(session.object(metric))
print(session.catalog.relations(metric))  # declared or unknown, not a join guarantee
print(session.catalog.search(kind="dimension", text="department", compatible_with=metric))
print(session.catalog.search(kind="time_dimension"))
# Copy actual references from this caller-visible catalog into the invocation.
# session.register(group_metric)
# trial = await session.run(group_metric, metric=metric,
#     group=selected_dimension,
#     scope=Scope(selected_period, selected_time),
#     filters=[Filter(member=selected_filter_dimension, operator="equals", values=[selected_value])])
session.close()
```

Discovery returns caller-visible objects. `compatible_with` validates the reference as a discovery hint; it does not remove unknown joins or guarantee queryability. The provider validates actual combinations.

## 5. Edit, debug and share

After editing, use `session.register(group_metric, replace=True)`. Ordinary breakpoints work; inspect `session.last_trial.attempts` for successful/failed requests and labels. Direct execution stays in the caller process and is not a stored Run. `session.preview(recipe, step_index=..., scope=...)` executes a fresh Recipe prefix through the same RunEngine.

For deployment, install reviewed modules in the server environment and register them in server bootstrap. Import does not register automatically; Web cannot upload Python. Use a Recipe to compose existing Methods into an organizational investigation.

Next: [authoring patterns](method-patterns.md), [manual scenarios](method-scenarios.md), [advanced analysis](statistical-methods.md), [internal contract](../reference/method-contract.md).

## Inspect the registered Method

Use a docstring to explain its purpose once. `session.find_methods()` returns registered contracts and requirement checks without querying data. See [Method discovery](method-discovery.md) for the shared Python, REST, Web and MCP flow, ambiguous questions and compatibility.

## Default MVP and optional extensions

The initial product exposes three query Methods and two small DoWhy analyses:

| Method | Purpose |
| --- | --- |
| `analysis.metric_lookup` (Skill) | Look up governed metric values |
| `analysis.trend` (Skill) | Inspect time trends and compare periods |
| `query.drilldown` | Break values and changes down by groups, then investigate a branch |
| `stats.binary_matching` | DoWhy matching contrast for treated units (ATT) |
| `stats.regression_adjustment` | DoWhy OLS change per stored treatment unit, or an explicit contrast |

A Recipe composes them into a reusable investigation. Peer comparison, unit analyses
and other statistical methods are optional. The DoWhy estimates retain unverified causal assumptions. Existing explicit Recipe references keep their
original execution contracts.

Enable a reviewed optional implementation in server startup code with the existing registry:

```python
from decision_layer.methods import registry
from decision_layer.methods.peer_comparison import PeerComparison

registry.register(PeerComparison())
```

For OLS, after installing the documented stats extra:

```python
from decision_layer.methods import registry
from decision_layer.methods.advanced import ols

registry.register(ols)
```

Registration exposes the same contract through Web, REST and MCP. In a local session
that already has compatibility implementations, use `session.register(ols, replace=True)`.
Keep registration in reviewed startup code so it runs after a server restart. This is
ordinary Python extension, not an interactive plugin installer. A marketplace and
Web plugin management are deferred. The default Method list is not an access control:
explicit historical Recipe references still execute with normal authorization and validation.

## Connected query Skills (ADR-098/103)

The notebook's final section runs analysis.drilldown → analysis.peer_comparison.
The client calls run_skill_query/finish_skill_step; the shared engine records real
queries, failures, selections and scope. Web shows waiting states and query logs.
No household-regression stage is appended. Separate registered Python stages can
still consume selection evidence through DataInput; the earlier function example
teaches that path. The notebook uses fixtures, not a live Claude experiment.

## 조회 Skill과 계산 분리 (ADR-099/103)

기본 지표 조회·추이는 한국어 `analysis.metric_lookup`, `analysis.trend` Skill입니다.
공통 실행기에 실제 조회와 결과를 기록합니다. 기간 변화·시계열 진단·예제 가구 회귀는
새 Method 목록에서 제외했습니다. 필요한 계산이 제공되지 않으면 해당 주장을 중단하며,
Skill 문장이나 AI의 임의 계산을 검증 근거로 쓰지 않습니다.

드릴다운·추이 지침은 1.1.0입니다. 과거 버전을 고정한 Recipe와 Run은 유지합니다.
현재 `campaign_recipe()` 1.1.0은 드릴다운 → peer 조회의 두 단계입니다.
과거 세 단계 실험은 `legacy_campaign_recipe()`로 명시적으로 재현합니다.

## Web에서 코드와 Skill 수정 (ADR-100)

Method 상세에서 Python 진입·보조 코드 또는 서식 있는 Skill을 읽습니다. 수정은
현재 버전에서 새 초안을 만들고, 저장 → 구문·등록 검사 → 검토 확인 → 새 버전 게시
순서입니다. 검사 통과는 실제 데이터나 분석 품질의 검증이 아닙니다. Python 검사와
게시는 신뢰한 운영자 코드를 실행하며, Method 게시 권한이 별도로 필요합니다.

일반 설치는 `DL_METHOD_ASSETS_DIR`와 `DL_ALLOW_METHOD_EDITING=true`로 운영자가
활성화합니다. `DL_METHOD_EDITORS`/`DL_METHOD_PUBLISHERS`는 Recipe 역할과 별개입니다.
현재 local/demo만 지원하며 공유 환경의 임의 코드 sandbox는 없습니다. 예제 Compose는
기존 data 볼륨의 `/data/method-assets`를 사용합니다. UI 게시 파일과 원래 Git 모듈은
별도 버전 원본이며, Git 반영은 명시적으로 검토·이관합니다.

새 Run은 선택된 코드와 해시를 저장합니다. 과거 Run에 코드가 없으면 현재 코드로
대신 표시하지 않습니다. 이전에 등록된 버전은 고정 Recipe에서 계속 선택할 수 있으며,
설치되지 않은 버전은 거부합니다. 외부 라이브러리 전체와 환경 재현은 별도 관리합니다.

### Authoring code versus complete source

New calculations still start with an ordinary function and `python_method`/`DataInput`.
Method detail shows the selected asset's required definitions and registration;
the draft starts from that module rather than unrelated Methods, Recipes or fixtures.
Exact source/hashes are separately expandable. Dynamic initialization falls back to
full source. Series diagnostics 1.1.0 is a real pandas calculation split: its existing
source-aware adapter retains extraction/checks/results, and 1.0.0 remains pinned-version
compatible. The specialized series adapter is not a new required authoring framework.

### Edit directly in Method detail

Use **Skill.md 편집** or **Python 편집** above the content. The document becomes a
syntax-aware editor with line numbers, search/replace and undo. Preview and comparison
tabs keep the editing buffer. Cmd/Ctrl+S saves a server draft. Registration checking
saves the current draft first; Python still requires trusted-code review. Publication
remains an explicit versioned action after checks/review. Pinned Recipes and old Runs
are not updated. Read mode retains edits; in-app link navigation offers save/continue/
discard, and refresh/close use the browser's unsaved warning. Saved drafts can be
reopened, edits typed during a save remain unsaved, and conflicts require explicit
comparison/reconciliation without silently replacing local text.
