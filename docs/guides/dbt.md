# Connect dbt Semantic Layer

Connect your existing dbt Semantic Layer through its official GraphQL API. Decision Layer discovers metrics and dimensions, submits queries and records the results in Runs. Your dbt environment handles SQL generation and warehouse access.

You do not need to install a gateway, upload a dbt project, share warehouse credentials or add Decision Layer metadata to your models.

## Connect

Start Decision Layer against your own source from the repository root:

```bash
docker compose up -d --build --wait
```

This root-level command starts only Web and API. The [local sample](../index.md) is a separate option under `examples/complete-journey`.

Open [Sources](http://localhost:3000/sources), choose **dbt Semantic Layer**, then enter:

| Field | Value |
| --- | --- |
| API URL | The Semantic Layer GraphQL endpoint shown for your dbt deployment |
| Environment ID | The deployment environment with your published semantic models |
| Connection name | A stable name, such as `analytics-production`, used in saved metric references |
| Access token | A dbt service token or personal access token with access to that environment |

For a North America multi-tenant deployment, the endpoint is `https://semantic-layer.cloud.getdbt.com/api/graphql`. Other regions, single-tenant and multi-cell deployments use different hosts. Copy your actual endpoint from dbt's connection settings; do not use the Administrative API URL.

Select **Test connection**, then **Save settings** and **Explore metrics**. A token needs the relevant Semantic Layer and metadata permissions. See dbt's [GraphQL documentation](https://docs.getdbt.com/docs/dbt-apis/sl-graphql) for deployment endpoints and token requirements.

The token is passed through to dbt on each request and kept only in the browser tab, not saved in Decision Layer's database. Your token controls which dbt environment and data can be queried. A shared service token represents shared access; it does not provide separate employee identities or application login.

## Analyze through MCP

Follow the [MCP setup](mcp.md) and provide the same token as `DL_TOKEN` in the MCP client's private environment. `DL_API_URL` remains the Decision Layer API address, for example `http://localhost:8000`.

Ask your client to list the available metrics and analyze one with registered Methods. Runs retain the question, settings, dbt query ID, semantic references and SQL when requested and returned by dbt. Web and MCP use the same execution engine. Use the same connection and token to see the same records.

## What is supported

- Metric and dimension discovery, including catalog pagination.
- Aggregate queries with categorical grouping, supported time grains, date ranges, ordering and bounded result pagination.
- Typed equality, inequality, comparison and null filters on categorical dimensions. Free-form SQL and Jinja input are not accepted.
- Query submission, completion polling and query-ID provenance.
- Drilldown, trend and descriptive peer comparisons through the common Methods.

Entity-grain extraction is not implemented. Statistical Methods still require their usual sample and grain information. `SIMPLE` alone does not prove that a metric is a sum or count; unknown aggregation/sample semantics stay unknown. Native ratio components are retained when visible. No custom `meta` is required to connect.

The adapter is tested against the documented GraphQL contract, including errors, pagination and timeout behavior. An authenticated production smoke test requires a real dbt environment; the bundled local example does not certify the hosted API connection.

## Environment configuration

The API process can also read `DL_SOURCE_PROVIDER=dbt`, `DBT_API_URL`, `DBT_ENVIRONMENT_ID` and `DBT_INSTANCE`. These override the corresponding saved settings. Pass them into your API container if you manage connections through deployment configuration. Tokens remain request credentials; use `DL_TOKEN` in MCP and the token field in Web.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Authentication or permission error | Token access to the selected environment, Semantic Layer and metadata permissions |
| Empty catalog | Metrics are defined and deployed in that environment |
| Wrong endpoint response | Use the regional Semantic Layer GraphQL endpoint, not a dbt job or admin API |
| Query failed | Inspect the query ID in dbt; verify compatible metrics, dimensions and filters |
| Query timed out | Check the recorded provider query ID before retrying; a remote query can continue after the client stops waiting |
| dbt Core project only | The official API requires a dbt platform Semantic Layer environment; dbt Core alone does not provide it. |
