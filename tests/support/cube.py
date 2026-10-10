"""Scripted Cube transport shared by provider/API contract tests."""
class FakeClient:
    def __init__(self, meta, rows_total=0):
        self._meta, self.rows_total, self.loads, self.sqls = meta, rows_total, [], []

    async def meta(self, token):
        return self._meta

    async def load(self, query, token):
        self.loads.append(query)
        start, n = query["offset"], query["limit"]
        keys = [*query.get("dimensions", []), *query.get("measures", [])]
        return {"data": [{k: (str(i) if k.endswith(("count", "rate")) else f"O{i}") for k in keys}
                         for i in range(start, min(start + n, self.rows_total))]}

    async def sql(self, query, token):
        self.sqls.append(query)
        return {"sql": {"sql": ["SELECT 1", []]}}
