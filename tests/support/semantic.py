"""Synthetic provider and independently calculated order fixtures shared by tests."""
from datetime import date, timedelta
import jwt
from decision_layer.core.errors import ProviderAccessDenied, UnknownSemanticObject
from decision_layer.core.models import Column, Dataset, DatasetSpec, ProviderCapabilities, QueryProvenance
from decision_layer.methods import ExecutionContext, Scope
from decision_layer.semantic.credentials import RequestCredentials
from decision_layer.semantic.providers.cube.catalog_mapper import map_meta


def ref(member):
    cube, name = member.split('.')
    return f"cube://local/{cube}/{name}"


RR, COUNT, RET = ref("ecom_order.return_rate"), ref("ecom_order.count"), ref("ecom_return.count")
AMOUNT, AOV = ref("ecom_order.total_order_amount"), ref("ecom_order.avg_order_value")
CAT, SELLER, DT = ref("ecom_product.category_nm"), ref("ecom_order.seller_id"), ref("ecom_order.order_dt")
CHANNEL, ORDER = ref("ecom_order.channel"), ref("ecom_order.order_id")
Q3, Q2 = ("2026-07-01", "2026-09-30"), ("2026-04-01", "2026-06-30")
CREDS = RequestCredentials("t")


def _orders():
    plan = {
        Q3: [("A", "S1", 100, 40), *[("A", s, 100, 15) for s in ("S2", "S3", "S4", "S5")], ("A", "S8", 5, 5),
             ("B", "S6", 250, 25), ("B", "S7", 250, 25)],
        Q2: [*[("A", s, 100, 15) for s in ("S1", "S2", "S3", "S4", "S5")], ("B", "S6", 250, 25), ("B", "S7", 250, 25)],
    }
    rows = []
    for (start, end), groups in plan.items():
        d0, days = date.fromisoformat(start), (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        i = 0
        for cat, seller, n, returns in groups:
            for k in range(n):
                rows.append({CAT: cat, SELLER: seller, DT: (d0 + timedelta(days=i % days)).isoformat(),
                             "returned": k < returns, "amount": 10_000 if cat == "A" else 20_000,
                             CHANNEL: "app" if k % 2 else "web", ORDER: f"{start[5:7]}-{len(rows)}"})
                i += 1
        rows[-1][DT] = end  # data is fresh up to the period end
    return rows


MEASURES = {
    COUNT: lambda g: float(len(g)),
    RET: lambda g: float(sum(o["returned"] for o in g)),
    RR: lambda g: 100.0 * sum(o["returned"] for o in g) / len(g) if g else None,
    AMOUNT: lambda g: float(sum(o["amount"] for o in g)),
    AOV: lambda g: sum(o["amount"] for o in g) / len(g) if g else None,
}


class FakeProvider:
    name, instance = "cube", "local"

    def __init__(self, cube_meta):
        self.catalog, _ = map_meta(cube_meta, "local")
        # The test provider declares known sample semantics; Cube /meta does not.
        for obj in self.catalog.objects:
            if obj.ref in (RR, AMOUNT, AOV):
                obj.count_measure = COUNT
        self.catalog.get(RR).metric_kind = "ratio"
        self.catalog.get(RR).ratio_parts = (RET, COUNT)
        self.catalog.get(AOV).metric_kind = "ratio"
        self.catalog.get(AOV).ratio_parts = (AMOUNT, COUNT)
        self.orders = _orders()
        self.calls = 0

    async def discover(self, credentials):
        token = getattr(credentials, "token", None)
        if token == "bad":
            raise ProviderAccessDenied("Cube 권한 오류: invalid token")
        try:
            groups = jwt.decode(token, options={"verify_signature": False}).get("groups", []) if token else []
        except jwt.PyJWTError:
            groups = []
        if "limited" in groups:
            return self.catalog.model_copy(update={"objects": [o for o in self.catalog.objects if o.ref != RR]})
        return self.catalog

    async def resolve(self, refs, credentials):
        catalog = await self.discover(credentials)
        objects = []
        for ref in refs:
            obj = catalog.get(ref)
            if obj is None:
                raise UnknownSemanticObject(f"'{ref}' was not found or you don't have access to it", ref=ref)
            objects.append(obj)
        return objects

    def capabilities(self):
        return ProviderCapabilities(aggregate_queries=True, entity_grain_queries=True, time_dimensions=True,
            compiled_sql=False, hierarchies=False, max_rows_per_query=50000)

    async def validate_dataset(self, spec, credentials):
        await self.resolve([*spec.measures, *spec.dimensions], credentials)

    async def execute(self, spec: DatasetSpec, credentials, *, with_sql=False) -> Dataset:
        self.calls += 1
        rows = self.orders
        if spec.time and spec.time.date_range:
            lo, hi = spec.time.date_range
            rows = [o for o in rows if lo <= o[DT] <= hi]
        for f in spec.filters:
            if f.operator == "equals":
                rows = [o for o in rows if o[f.member] in f.values]
            elif f.operator == "notEquals":
                rows = [o for o in rows if o[f.member] not in f.values]
            else:
                raise NotImplementedError(f.operator)
        keys = ([spec.entity] if spec.grain == "entity" else []) + list(spec.dimensions) \
            + ([DT] if spec.time and spec.time.granularity else [])
        groups: dict[tuple, list] = {}
        for o in rows:
            groups.setdefault(tuple(o[k] for k in keys), []).append(o)
        if not keys:
            groups = {(): rows}
        out = [[*k, *(MEASURES[m](g) for m in spec.measures)] for k, g in groups.items()]
        for member, direction in spec.order:
            i = [*keys, *spec.measures].index(member)
            out.sort(key=lambda r: r[i], reverse=direction == "desc")
        out = out[: spec.limit_rows] if spec.limit_rows else out
        cols = [Column(ref=k, role="dimension", data_type="string") for k in keys] + \
               [Column(ref=m, role="measure", data_type="number") for m in spec.measures]
        prov = QueryProvenance(provider="cube", instance="local", native_query={}, rows=len(out), elapsed_ms=0)
        return Dataset(spec=spec, columns=cols, rows=out, provenance=[prov])


def ctx(provider, date_range=Q3, **kw):
    return ExecutionContext(provider=provider, credentials=CREDS, catalog=provider.catalog,
                            scope=Scope(date_range=date_range, **kw))
