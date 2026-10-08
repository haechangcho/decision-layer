# dbt Model Reference

SQL and YAML models for the same source tables used by the Cube sample. These are
reference definitions, not a bundled dbt API server or a tested hosted deployment.

To use them, configure the source schema and warehouse connection in your own dbt
project, build and deploy the models, and publish the metrics in a dbt platform
Semantic Layer environment. Connect Decision Layer to its official GraphQL API
with the endpoint, environment ID and access token. See the
[connection guide](../../../docs/guides/dbt.md).

The official Semantic Layer service and API are hosted dbt components, not an
open-source Docker service.
Sample model definitions do not override the adapter's capability checks: analyses
requiring unavailable count, aggregation or entity semantics still fail closed.

To test the same local sample in a Snowflake trial, use the
[sample copy guide](../snowflake/README.md). Set `journey_database` to the copied
source database if it differs from the dbt target database. The SQL time spine
supports PostgreSQL and Snowflake; hosted deployment still requires live validation.
