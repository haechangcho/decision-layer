# %% [markdown]
# # Query Method 작성과 파이프라인 디버깅
#
# 이 파일은 Jupyter/VS Code용 셀 형식 예제입니다. 함께 제공되는 ipynb에서도 실행할 수 있습니다.
# 현재 Decision Layer API를 사용합니다. 아직 구현되지 않은 SDK 함수는 사용하지 않습니다.
# Cube catalog 탐색 → 지표/차원 선택 → Method 작성 → 로컬 등록 → 직접 실행 →
# 2단계 Recipe preview → 입력/쿼리/검증 확인 순서입니다.
#
# 준비: 저장소에서 `python -m pip install -e .`를 실행한 Python 커널을 선택합니다.
# Cube의 API URL, 사용자 token, 분석 참조와 기간은 환경변수로 전달합니다.
# token은 노트북에 저장하거나 출력하지 않습니다.

# %%
import os
from pprint import pprint

from decision_layer.auth import identify
from decision_layer.core.models import (
    Artifact, DatasetSpec, MethodManifest, ParamSpec, PlanStep,
    Recipe, RoleSpec, SemanticScope,
)
from decision_layer.methods import registry as builtins
from decision_layer.methods.base import Method, MethodOutput, MethodRegistry
from decision_layer.methods.context import ExecutionContext, Refused, Scope
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.store import MemoryRunStore
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.cube.client import CubeClient
from decision_layer.semantic.providers.cube.provider import CubeProvider
from decision_layer.validation.builtin import non_empty

provider = CubeProvider(
    CubeClient(os.environ["CUBE_API_URL"]),  # .../cubejs-api/v1
    instance=os.environ.get("CUBE_INSTANCE", "local"),
)
creds = RequestCredentials(os.environ["CUBE_TOKEN"])
caller = await identify(provider, creds)

# %% [markdown]
# ## Semantic layer API에서 metric과 dimension 탐색
#
# discover는 Cube /meta를 호출하고 현재 사용자가 볼 수 있는 객체를 가져옵니다.
# 지표의 수식과 join은 semantic layer에 남습니다.

# %%
catalog = await provider.discover(creds)
metrics = [obj for obj in catalog.objects if obj.public and obj.kind == "measure"]
dimensions = [obj for obj in catalog.objects if obj.public and obj.kind == "dimension"]

pprint([{"ref": obj.ref, "title": obj.title,
         "dimensions": obj.dimension_refs, "time_dimension": obj.time_dimension}
        for obj in metrics])
pprint([{"ref": obj.ref, "title": obj.title, "type": obj.data_type}
        for obj in dimensions])

# %% [markdown]
# ## 분석할 객체와 기간 선택
#
# 위 목록에서 참조를 복사해 환경변수에 지정하거나 아래 변수를 직접 편집합니다.
# 객체를 임의로 첫 번째 항목에서 고르지 않습니다. metadata의 차원 관계는 탐색용이며,
# 실제 조합의 지원 여부는 provider가 데이터 요청 시 확인합니다.

# %%
metric = os.environ["CUBE_METRIC"]
dimension = os.environ["CUBE_DIMENSION"]
time_dimension = os.environ["CUBE_TIME_DIMENSION"]
date_range = (os.environ["ANALYSIS_START"], os.environ["ANALYSIS_END"])

for ref, kind in ((metric, "measure"), (dimension, "dimension"),
                  (time_dimension, "time_dimension")):
    obj = catalog.get(ref)
    assert obj is not None and obj.public and obj.kind == kind, (ref, kind)

scope = Scope(date_range=date_range, time_dimension=time_dimension)

# %% [markdown]
# ## Query Method 작성
#
# 목표: 선택한 지표를 한 차원으로 나누고 값이 큰 N개 그룹을 반환합니다.
# 지표를 재계산하지 않습니다. 정렬과 집계는 Cube가 수행합니다.
# 이 예제는 상위 N개 조회이며 전체 모집단의 비중·총변화 기여도·통계적 유의성을 주장하지 않습니다.
# 현재 manifest의 legacy kind 필드는 query로 지정합니다.

# %%
class GroupMetric(Method):
    manifest = MethodManifest(
        name="example.group_metric", version="1.0.0", kind="query",
        label="Metric by group",
        description="Retrieve the largest metric values by a selected dimension.",
        roles={
            "metric": RoleSpec(kind="measure", description="Existing governed metric"),
            "dimension": RoleSpec(kind="dimension", description="Grouping dimension"),
        },
        parameters={
            "limit": ParamSpec(type="integer", default=5, minimum=1, maximum=100),
        },
        execution="semantic_pushdown", interpretation="descriptive",
        outputs=["table"], provides=["group_metric_lookup"],
    )

    async def run(self, ctx, bindings, params):
        if not ctx.provider.capabilities().aggregate_queries:
            raise Refused("The provider does not support aggregate queries.")

        # 이 줄 앞뒤에 breakpoint()를 두고 직접 실행 셀에서 확인할 수 있습니다.
        dataset = await ctx.dataset(DatasetSpec(
            grain="aggregate",
            measures=[bindings["metric"]],
            dimensions=[bindings["dimension"]],
            time=ctx.time_scope(bindings["metric"]),
            filters=ctx.scope.filters,
            order=[(bindings["metric"], "desc")],
            limit_rows=params["limit"],
        ), with_sql=ctx.provider.capabilities().compiled_sql)

        columns = [column.ref for column in dataset.columns]
        rows = [dict(zip(columns, row)) for row in dataset.rows]
        return MethodOutput(
            primary=Artifact(type="table", title="Metric by group", data=rows),
            validation=[non_empty(len(rows))],
            warnings=["Top-N lookup only; it does not establish complete population coverage."],
        )

# %% [markdown]
# ## 로컬 등록과 셀 단위 디버깅
#
# 이 registry는 노트북 전용입니다. 서버의 전역 registry는 변경하지 않습니다.
# 이 셀을 다시 실행하면 새 registry에 수정한 Method가 등록됩니다.
# 직접 실행은 커널의 현재 이벤트 루프에서 수행되어 중간 변수를 조사하기 쉽습니다.
# Result provenance는 남지만 이 호출 자체는 저장된 Run을 만들지 않습니다.

# %%
methods = MethodRegistry()
methods.register(builtins.get("query.aggregate"))
methods.register(GroupMetric())

ctx = ExecutionContext(provider=provider, credentials=creds,
                       catalog=catalog, scope=scope, max_queries=5)
result = await methods.run(
    "example.group_metric", ctx,
    bindings={"metric": metric, "dimension": dimension},
    params={"limit": 3},
)
pprint(result.model_dump(mode="json"))
assert result.status == "success", result.warnings
assert result.provenance.queries

# %% [markdown]
# ## 같은 Method를 2단계 파이프라인에 넣기
#
# 1단계: 지표 전체 값 조회. 2단계: 새 Method로 그룹별 조회.
# Recipe preview는 실제 RunEngine을 사용하며 메모리에 Run evidence를 저장합니다.
# preview의 step_index=0은 첫 단계만, step_index=1은 두 단계 전체를 새로 실행합니다.
# 중간 Run을 이어 실행하는 기능이 아니므로 실행할 때마다 쿼리가 다시 나갑니다.

# %%
recipe = Recipe(
    name="group_metric_example", version="1.0.0",
    description="Inspect an existing metric overall and by group.",
    mode="pipeline",
    semantic_scope=SemanticScope(primary_metric=metric,
                                 preferred_dimensions=[dimension]),
    steps=[
        PlanStep(id="overall", method="query.aggregate",
                 bindings={"metric": metric}),
        PlanStep(id="groups", method="example.group_metric",
                 bindings={"metric": metric, "dimension": dimension},
                 params={"limit": 3}),
    ],
)
engine = RunEngine(
    provider, RecipeStore(None, "cube", provider.instance), MemoryRunStore(),
    registry=methods,
)
run = await engine.preview(
    creds, caller, recipe, step_index=1,
    scope={"date_range": list(date_range), "time_dimension": time_dimension},
)

# %% [markdown]
# ## 각 단계의 입력과 출력 확인
#
# preview Run의 completed는 실행이 끝났다는 뜻입니다. 각 Result의 status와 validation을
# 확인해야 합니다. 실패한 provider 요청도 query_attempts에 남습니다.

# %%
for record in run.steps:
    pprint({"step": record.step.id, "method": record.step.method,
            "bindings": record.step.bindings, "params": record.step.params,
            "status": record.result.status,
            "output": record.result.primary.model_dump() if record.result.primary else None,
            "validation": [check.model_dump() for check in record.result.validation],
            "warnings": record.result.warnings})

for attempt in run.query_attempts:
    pprint({"step": attempt.step_id, "status": attempt.status,
            "dataset_spec": attempt.spec.model_dump(mode="json"),
            "error_code": attempt.error_code})

for record in run.steps:
    for query in record.result.provenance.queries:
        pprint({"step": record.step.id, "native_query": query.native_query,
                "sql": query.compiled_sql, "rows": query.rows,
                "elapsed_ms": query.elapsed_ms})

assert len(run.steps) == 2
assert all(record.result.status == "success" for record in run.steps)

# %% [markdown]
# ## 입력 오류를 테스트하고 수정 반복
#
# limit을 0으로 바꾸면 쿼리 전 공통 파라미터 검사에서 거절되어야 합니다.
# 수치 정답 테스트에는 별도의 작은 fixture와 손계산한 예상값이 필요합니다.
# 실제 데이터의 현행 출력 자체를 정답으로 삼지 않습니다.

# %%
from decision_layer.methods.base import InvalidBinding

before = len(ctx.queries)
try:
    await methods.run("example.group_metric", ctx,
                     {"metric": metric, "dimension": dimension}, {"limit": 0})
except InvalidBinding as exc:
    print(exc.message)
else:
    raise AssertionError("An invalid limit was accepted")
assert len(ctx.queries) == before

# Method를 수정한 뒤 등록 셀과 직접 실행 셀을 다시 실행합니다.
# Recipe params를 수정한 뒤 preview 셀을 다시 실행하면 새 Run에서 비교할 수 있습니다.
engine.jobs.shutdown()
