"""Translate canonical datasets into dbt's public Semantic Layer GraphQL API.

Contract: https://docs.getdbt.com/docs/dbt-apis/sl-graphql
No dbt project, warehouse credentials or local MetricFlow runtime is required.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
import json
import math
import re
import time

import httpx

from ....core.errors import CapabilityMissing, DatasetTooLarge, InvalidDatasetSpec, ProviderAccessDenied, ProviderError, UnknownSemanticObject
from ....core.models import Column, Dataset, DatasetSpec, ProviderCapabilities, QueryProvenance, SemanticCatalog, SemanticObject

CATALOG = """query Catalog($environmentId: BigInt!, $pageNum: Int!) {
  metricsPaginated(environmentId: $environmentId, pageNum: $pageNum, pageSize: 100) {
    totalPages
    items { name description type
      typeParams { numerator { name } denominator { name } }
      dimensions { name description type queryableGranularities }
      queryableGranularities
    }
  }
}"""
CREATE = """mutation Analyze($environmentId: BigInt!, $metrics: [MetricInput!]!,
  $groupBy: [GroupByInput!], $where: [WhereInput!], $orderBy: [OrderByInput!], $limit: Int) {
  createQuery(environmentId: $environmentId, metrics: $metrics, groupBy: $groupBy,
    where: $where, orderBy: $orderBy, limit: $limit) { queryId }
}"""
RESULT = """query Result($environmentId: BigInt!, $queryId: String!, $pageNum: Int!, $withSql: Boolean!) {
  query(environmentId: $environmentId, queryId: $queryId, pageNum: $pageNum) {
    status error totalPages sql @include(if: $withSql)
    jsonResult(orient: TABLE, encoded: false)
  }
}"""
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_ROWS = 50000


def _literal(value):
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (float, int)):
        if not math.isfinite(value):
            raise InvalidDatasetSpec("Filter values must be finite.")
        return str(value)
    # dbt evaluates Jinja before warehouse SQL. Backslash escaping varies by dialect.
    if not isinstance(value, str) or any(x in value for x in ("\\", "\x00", "{{", "{%", "{#")):
        raise CapabilityMissing("This filter value requires escaping that is not supported by the dbt adapter.")
    return "'" + value.replace("'", "''") + "'"


class DbtSemanticLayerProvider:
    name = "dbt"
    identity_mode = "credential"

    def __init__(self, api_url: str, instance: str, environment_id: int | None = None,
                 *, timeout: float = 120, poll_interval: float = 1):
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/api/graphql"):
            self.api_url += "/api/graphql"
        self.instance, self.environment_id = instance, environment_id
        self.timeout, self.poll_interval = timeout, poll_interval

    def capabilities(self):
        return ProviderCapabilities(aggregate_queries=True, entity_grain_queries=False,
                                    time_dimensions=True, compiled_sql=True, hierarchies=False,
                                    max_rows_per_query=MAX_ROWS)

    async def _request(self, client, query, variables, credentials):
        if not self.api_url.startswith("https://"):
            raise InvalidDatasetSpec("Use an HTTPS endpoint for the hosted dbt Semantic Layer.")
        token = credentials.bearer()
        if not token:
            raise ProviderAccessDenied("Enter a dbt Semantic Layer service token or personal access token.")
        if not self.environment_id:
            raise InvalidDatasetSpec("Enter the dbt deployment environment ID in Sources.")
        try:
            response = await client.post(self.api_url, headers={"Authorization": f"Bearer {token}"},
                                         json={"query": query, "variables": {"environmentId": self.environment_id, **variables}})
        except httpx.RequestError as exc:
            raise ProviderError("Could not reach dbt Semantic Layer. Check the endpoint and network connection.") from exc
        if response.status_code in (401, 403):
            raise ProviderAccessDenied("dbt rejected the token or environment access. Check Semantic Layer and metadata permissions.")
        if response.status_code == 429:
            raise ProviderError("dbt Semantic Layer rate limit reached. Retry the analysis later.")
        if not response.is_success:
            raise ProviderError("dbt Semantic Layer returned an HTTP error. Check the endpoint and service status.", status=response.status_code)
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError("The endpoint did not return GraphQL JSON. Use the dbt Semantic Layer endpoint.") from exc
        if not isinstance(body, dict):
            raise ProviderError("dbt returned an invalid GraphQL response.")
        if body.get("errors"):
            codes = {str(e.get("extensions", {}).get("code", "")).upper() for e in body["errors"] if isinstance(e, dict)}
            if codes & {"UNAUTHENTICATED", "FORBIDDEN", "UNAUTHORIZED"}:
                raise ProviderAccessDenied("dbt denied access. Check the token's Semantic Layer permissions and environment ID.")
            # Provider errors can contain SQL or credentials; do not echo arbitrary payloads.
            raise ProviderError("dbt rejected the GraphQL request. Check the environment, metric compatibility and Semantic Layer query logs.")
        if not isinstance(body.get("data"), dict):
            raise ProviderError("dbt returned no GraphQL data.")
        return body["data"]

    def _ref(self, collection, name):
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise ProviderError("dbt returned an unsupported semantic object name.")
        return f"dbt://{self.instance}/{collection}/{name}"

    async def discover(self, credentials):
        objects, metrics, page = {}, [], 1
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            while True:
                data = await self._request(client, CATALOG, {"pageNum": page}, credentials)
                result = data.get("metricsPaginated")
                if not isinstance(result, dict) or not isinstance(result.get("items"), list):
                    raise ProviderError("dbt returned an invalid metric catalog.")
                metrics.extend(result["items"])
                pages = result.get("totalPages", 1)
                if not isinstance(pages, int) or pages > 1000:
                    raise ProviderError("The dbt catalog exceeds the supported page limit.")
                if page >= pages:
                    break
                page += 1
        for item in metrics:
            dimensions = []
            dims = list(item.get("dimensions") or [])
            if item.get("queryableGranularities") and not any(d["name"] == "metric_time" for d in dims):
                dims.append({"name": "metric_time", "type": "TIME", "queryableGranularities": item["queryableGranularities"]})
            for dim in dims:
                ref = self._ref("dimensions", dim["name"])
                dimensions.append(ref)
                is_time = dim["type"] == "TIME"
                objects[ref] = SemanticObject(ref=ref, kind="time_dimension" if is_time else "dimension",
                    data_type="time" if is_time else "string", title=dim["name"].replace("__", " / ").replace("_", " "),
                    description=dim.get("description"), metadata={"native_name": dim["name"],
                        "queryable_granularities": dim.get("queryableGranularities", [])})
            ref = self._ref("metrics", item["name"])
            params = item.get("typeParams") or {}
            num, den = params.get("numerator"), params.get("denominator")
            parts = (self._ref("metrics", num["name"]), self._ref("metrics", den["name"])) if item["type"] == "RATIO" and num and den else None
            objects[ref] = SemanticObject(ref=ref, kind="measure", data_type="number",
                title=item["name"].replace("_", " "), description=item.get("description"),
                metric_kind="ratio" if parts else "other", ratio_parts=parts, dimension_refs=dimensions,
                time_dimension=self._ref("dimensions", "metric_time") if self._ref("dimensions", "metric_time") in dimensions else None,
                metadata={"native_name": item["name"], "native_type": item["type"], "environment_id": self.environment_id,
                          "queryable_granularities": item.get("queryableGranularities", [])})
        # Keep inaccessible ratio components out of executable references.
        for obj in objects.values():
            if obj.ratio_parts and any(p not in objects for p in obj.ratio_parts):
                obj.ratio_parts = None
        return SemanticCatalog(provider=self.name, instance=self.instance, objects=list(objects.values()))

    async def resolve(self, refs, credentials):
        catalog = await self.discover(credentials)
        objects = [catalog.get(r) for r in refs]
        if any(o is None for o in objects):
            raise UnknownSemanticObject("A semantic reference is unavailable in this dbt environment.")
        return objects

    def _compile(self, spec, catalog):
        if spec.grain != "aggregate":
            raise CapabilityMissing("The dbt API adapter supports aggregate analysis; entity-grain analysis is unavailable.")
        refs = [*spec.measures, *spec.dimensions, *(f.member for f in spec.filters), *(r for r, _ in spec.order)]
        if spec.time:
            refs.append(spec.time.dimension)
        objects = {r: catalog.get(r) for r in refs}
        if any(o is None for o in objects.values()):
            raise UnknownSemanticObject("A requested metric or dimension is unavailable in this dbt environment.")
        if any(objects[r].kind != "measure" for r in spec.measures) or any(objects[r].kind != "dimension" for r in spec.dimensions):
            raise InvalidDatasetSpec("Select metrics and categorical dimensions in their respective roles.")
        requested_dims = set(spec.dimensions) | {f.member for f in spec.filters}
        if spec.time:
            requested_dims.add(spec.time.dimension)
        for metric in spec.measures:
            if not requested_dims.issubset(objects[metric].dimension_refs):
                raise InvalidDatasetSpec("A requested dimension is not available for every selected metric.")
        names = {r: o.metadata["native_name"] for r, o in objects.items()}
        metric_inputs = [{"name": names[r]} for r in dict.fromkeys(spec.measures)]
        groups = {r: {"name": names[r]} for r in dict.fromkeys(spec.dimensions)}
        columns = [Column(ref=r, role="dimension", data_type=objects[r].data_type) for r in groups]
        keys = [names[r] for r in groups]
        where = []
        if spec.time:
            obj = objects[spec.time.dimension]
            if obj.kind != "time_dimension":
                raise InvalidDatasetSpec("The selected date basis is not a time dimension.")
            if spec.time.granularity:
                grain = spec.time.granularity.upper()
                for metric in spec.measures:
                    if spec.time.dimension not in objects[metric].dimension_refs:
                        raise InvalidDatasetSpec("The selected time dimension is not available for every metric.")
                if grain not in obj.metadata["queryable_granularities"]:
                    raise CapabilityMissing("This time granularity is unavailable for the selected date basis.")
                groups[obj.ref] = {"name": names[obj.ref], "grain": grain}
                columns.append(Column(ref=obj.ref, role="time", data_type="time", granularity=spec.time.granularity))
                keys.append(names[obj.ref] + "__" + spec.time.granularity)
            if spec.time.date_range:
                try:
                    start, end = (date.fromisoformat(v) for v in spec.time.date_range)
                    if start > end:
                        raise ValueError()
                    until = end + timedelta(days=1)
                except (ValueError, OverflowError) as exc:
                    raise InvalidDatasetSpec("Choose a valid inclusive date range.") from exc
                field = "{{ TimeDimension('" + names[obj.ref] + "', 'day') }}"
                where.append({"sql": f"{field} >= '{start.isoformat()}' AND {field} < '{until.isoformat()}'"})
        for f in spec.filters:
            obj = objects[f.member]
            if obj.kind != "dimension":
                raise CapabilityMissing("dbt filters currently support categorical dimensions. Use the period control for dates.")
            field = "{{ Dimension('" + names[f.member] + "') }}"
            if f.operator in ("set", "notSet"):
                expression = field + (" IS NOT NULL" if f.operator == "set" else " IS NULL")
            elif f.operator in ("equals", "notEquals"):
                expression = field + (" IN (" if f.operator == "equals" else " NOT IN (") + ", ".join(_literal(v) for v in f.values) + ")"
            elif f.operator in ("gt", "gte", "lt", "lte") and len(f.values) == 1:
                expression = field + " " + {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[f.operator] + " " + _literal(f.values[0])
            else:
                raise CapabilityMissing("This filter operator is not supported by the dbt API adapter.")
            where.append({"sql": expression})
        order = []
        for ref, direction in spec.order:
            if ref in spec.measures:
                key = {"metric": {"name": names[ref]}}
            elif ref in groups:
                key = {"groupBy": groups[ref]}
            else:
                raise InvalidDatasetSpec("Sort by a selected metric or grouped dimension.")
            order.append({**key, "descending": direction == "desc"})
        for ref in dict.fromkeys(spec.measures):
            columns.append(Column(ref=ref, role="measure", data_type="number"))
            keys.append(names[ref])
        limit = spec.limit_rows
        if limit is not None and not 1 <= limit <= MAX_ROWS:
            raise DatasetTooLarge(f"Choose a row limit between 1 and {MAX_ROWS}.")
        return {"metrics": metric_inputs, "groupBy": list(groups.values()), "where": where,
                "orderBy": order, "limit": limit or MAX_ROWS + 1}, columns, keys

    async def validate_dataset(self, spec, credentials):
        self._compile(spec, await self.discover(credentials))

    async def execute(self, spec: DatasetSpec, credentials, *, with_sql=False):
        native, columns, keys = self._compile(spec, await self.discover(credentials))
        started = time.monotonic()
        rows, page, sql = [], 1, None
        try:
            async with asyncio.timeout(self.timeout), httpx.AsyncClient(timeout=min(30, self.timeout), follow_redirects=False) as client:
                created = await self._request(client, CREATE, native, credentials)
                query_id = (created.get("createQuery") or {}).get("queryId")
                if not query_id:
                    raise ProviderError("dbt did not return a query ID.")
                while True:
                    data = await self._request(client, RESULT, {"queryId": query_id, "pageNum": page, "withSql": with_sql}, credentials)
                    result = data.get("query") or {}
                    status = result.get("status")
                    if status in ("FAILED", "CANCELLED", "CANCELED"):
                        raise ProviderError("The dbt query failed. Inspect the query in dbt using its query ID.", query_id=query_id)
                    if status in ("PENDING", "RUNNING", "QUEUED", "CREATED", "COMPILING"):
                        await asyncio.sleep(self.poll_interval)
                        continue
                    if status != "SUCCESSFUL":
                        raise ProviderError("dbt returned an unknown query state.", query_id=query_id)
                    try:
                        table = json.loads(result["jsonResult"])
                        fields = {f["name"].lower(): f["name"] for f in table["schema"]["fields"]}
                        if any(k.lower() not in fields for k in keys):
                            raise ValueError("Missing result columns")
                        rows.extend([[r[fields[k.lower()]] for k in keys] for r in table["data"]])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ProviderError("dbt returned an unexpected result schema.", query_id=query_id) from exc
                    if len(rows) > MAX_ROWS:
                        raise DatasetTooLarge("The dbt result exceeds 50,000 rows. Narrow the period or filters.")
                    sql = result.get("sql") or sql
                    pages = result.get("totalPages", 1)
                    if not isinstance(pages, int) or pages < 1 or pages > MAX_ROWS:
                        raise ProviderError("dbt returned invalid result pagination.", query_id=query_id)
                    if page >= pages:
                        break
                    page += 1
        except TimeoutError as exc:
            raise ProviderError("The dbt query exceeded the wait limit. Check its status in dbt before retrying.",
                                query_id=locals().get("query_id")) from exc
        return Dataset(spec=spec, columns=columns, rows=rows, provenance=[QueryProvenance(
            provider=self.name, instance=self.instance, native_query={"environmentId": self.environment_id,
                "queryId": query_id, **native}, compiled_sql=sql, rows=len(rows), pages=page,
            elapsed_ms=round((time.monotonic() - started) * 1000))])
