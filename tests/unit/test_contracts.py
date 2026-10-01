import json

import pytest
from pydantic import ValidationError

from decision_layer.core.errors import InvalidReference
from decision_layer.core.ids import SemanticRef, method_ref, new_id, recipe_ref
from decision_layer.core.models import (
    AnalysisPlan, Artifact, Dataset, DatasetSpec, Filter, MethodManifest, PlanStep, Provenance, QueryProvenance,
    Recipe, Result, RoleSpec, Run, SemanticCatalog, SemanticObject, SemanticScope, TimeScope, ValidationResult,
)

R = "cube://local/ecom_order/return_rate"
SELLER = "cube://local/ecom_order/seller_id"
CATEGORY = "cube://local/ecom_product/category_nm"
ORDER_DT = "cube://local/ecom_order/order_dt"


def roundtrip(model):
    again = type(model).model_validate(json.loads(model.model_dump_json()))
    assert again == model
    return again


def test_semantic_ref_parse_and_build():
    ref = SemanticRef.parse(R)
    assert ref.member_name == "ecom_order.return_rate" and str(ref) == R
    assert SemanticRef.from_member("ecom_order.return_rate", "local") == ref
    for bad in ("ecom_order.return_rate", "cube://local/ecom_order", "cube://local/a/b/c"):
        with pytest.raises(InvalidReference):
            SemanticRef.parse(bad)


def test_versioned_refs_and_ids():
    assert method_ref("query.drilldown", "1.0.0") == "method://query/drilldown@1.0.0"
    assert recipe_ref("return_rate_investigation", "1.2.0") == "recipe://return-rate-investigation@1.2.0"
    a, b = new_id("run"), new_id("run")
    assert a.startswith("run_") and len(a) == 30 and a != b


def test_models_roundtrip():
    catalog = SemanticCatalog(provider="cube", instance="local", objects=[
        SemanticObject(ref=R, kind="measure", data_type="number", title="반품률(%)", metric_kind="ratio",
                       entity="cube://local/ecom_order/order_id"),
        SemanticObject(ref=SELLER, kind="dimension", data_type="string", title="판매자"),
    ], hierarchies={"cube://local/ecom_order/seller_org": ["cube://local/ecom_order/md_team_nm", SELLER]})
    roundtrip(catalog)
    assert catalog.get(SELLER).title == "판매자"

    spec = DatasetSpec(grain="aggregate", measures=[R], dimensions=[CATEGORY],
                       time=TimeScope(dimension=ORDER_DT, date_range=("2026-01-01", "2026-09-30")),
                       filters=[Filter(member=SELLER, operator="equals", values=["S017"])],
                       order=[(R, "desc")])
    roundtrip(spec)
    roundtrip(Dataset(spec=spec, columns=[], rows=[["여성의류", 22.81]], provenance=[
        QueryProvenance(provider="cube", instance="local", native_query={"measures": ["x"]}, rows=1, elapsed_ms=5)]))

    manifest = MethodManifest(name="query.drilldown", version="1.0.0", kind="query", description="",
                              roles={"metric": RoleSpec(kind="measure"), "dimensions": RoleSpec(kind="dimension", multiple=True)},
                              execution="semantic_pushdown", interpretation="descriptive", outputs=["breakdown_table"])
    roundtrip(manifest)

    recipe = Recipe(name="return_rate_investigation", version="1.0.0", description="",
                    semantic_scope=SemanticScope(primary_metric=R, preferred_dimensions=[CATEGORY, SELLER]),
                    mode="investigation", allowed_methods=["query.drilldown", "query.compare"])
    roundtrip(recipe)

    plan = AnalysisPlan(question="반품률이 왜 높아?", recipe="recipe://return-rate-investigation@1.0.0",
                        resolved={"primary_metric": R},
                        steps=[PlanStep(method="query.drilldown", bindings={"metric": R, "dimensions": [CATEGORY]})])
    result = Result(status="success", interpretation="descriptive",
                    primary=Artifact(type="breakdown_table", data=[{"category": "여성의류", "value": 16.73}]),
                    validation=[ValidationResult(validator="non_empty", status="pass", code="OK", message="")],
                    provenance=Provenance(method="method://query/drilldown@1.0.0", semantic_refs=[R, CATEGORY]))
    roundtrip(result)
    roundtrip(Run(id=new_id("run"), plan=plan, recipe_snapshot=recipe))


def test_contract_guards():
    with pytest.raises(ValidationError):
        DatasetSpec(grain="entity", measures=[R])                       # entity grain without entity
    with pytest.raises(ValidationError):
        Filter(member=SELLER, operator="equals")                        # values required
    with pytest.raises(ValidationError):
        Recipe(name="x", version="1.0.0", description="", mode="pipeline",
               semantic_scope=SemanticScope(primary_metric=R))          # pipeline without steps
    with pytest.raises(ValidationError):
        DatasetSpec(grain="aggregate", measures=["ecom_order.return_rate"])  # not a semantic ref
    with pytest.raises(ValidationError):
        AnalysisPlan(recipe="recipe://x")                                # unversioned
