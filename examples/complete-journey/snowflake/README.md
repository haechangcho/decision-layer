# Snowflake Trial Test

Copy the existing local retail example into a separate Snowflake trial database.
This is test setup, not a Decision Layer warehouse connector. Decision Layer still
connects to the official dbt Semantic Layer API, never directly to Snowflake.

The script copies eight source tables, the household table and the materialized
campaign outcomes. It preserves the fixed example dates and checks row counts,
total receipts and transaction date coverage. Campaign outcomes are a snapshot of
the local sample, not a Snowflake transformation pipeline.

## Export

From the repository root, with the Cube example running:

```sh
DATABASE_URL=postgresql://demo_loader:local-example-only@127.0.0.1:5433/journey \
  .venv/bin/python examples/complete-journey/snowflake/copy_sample.py export \
  --directory /tmp/decision-layer-snowflake-sample
```

Use a new empty directory. The script only reads the pinned sample database.

## Upload

Install the official connector into a separate test environment:

```sh
python3 -m venv /tmp/decision-layer-snowflake-tools
/tmp/decision-layer-snowflake-tools/bin/pip install 'snowflake-connector-python>=3.12,<5'
/tmp/decision-layer-snowflake-tools/bin/python \
  examples/complete-journey/snowflake/copy_sample.py upload \
  --directory /tmp/decision-layer-snowflake-sample \
  --account YOUR_ORGANIZATION-YOUR_ACCOUNT --user YOUR_USER
```

Enter your password at the terminal prompt. Enter an authenticator code at the
MFA prompt, or press Enter for push approval (or if MFA is not enrolled).
The script does not save credentials. Account identifiers are available in
Snowflake's account details; do not use the entire Snowsight URL.

This bootstrap uses your account administrator role to create `DL_JOURNEY_TEST`
and a dedicated `DL_TEST_WH` X-Small warehouse with 60-second auto-suspend. Loading
uses trial credits. Existing tables and warehouses are refused, not replaced. A
failed load may leave partial tables; use a fresh database and warehouse for a
retry. The warehouse is suspended after successful verification, and automatically
suspends when idle after a failure. No grants or service credentials are created.

## dbt

After a successful upload, create the limited test identity:

```sh
/tmp/decision-layer-snowflake-tools/bin/python \
  examples/complete-journey/snowflake/setup_dbt.py \
  --account YOUR_ORGANIZATION-YOUR_ACCOUNT --admin-user YOUR_USER \
  --keys-directory "$HOME/.config/decision-layer/snowflake-test"
```

Choose and confirm a private-key passphrase, then enter your administrator password
and MFA code. The encrypted PKCS#8 key is stored locally with owner-only access.
The script creates `DL_DBT_TEST`, assigns `DL_DBT_TEST_ROLE`, grants SELECT on the
ten sample tables, USAGE on the database and warehouse, and table/view creation
only in `ANALYTICS`. No future source-table or account-wide privileges are granted.
Existing identities and keys are refused. DDL is not transactional; after a partial
failure, review the created objects before retrying rather than deleting them blindly.

Select key-pair authentication in dbt. Use `DL_DBT_TEST` with
`DL_DBT_TEST_ROLE`, the encrypted key, its passphrase, and schema `ANALYTICS`.
Enter credentials directly in dbt. Do not commit them, paste them into chat, or
use the bootstrap administrator as dbt's execution identity.

Configure a Snowflake connection in dbt using a dedicated, limited-access identity,
not the bootstrap administrator. Configure source variable
`journey_database: DL_JOURNEY_TEST`, warehouse `DL_TEST_WH`, and a separate model
schema (for example `ANALYTICS`). Use the models in `../dbt` and build them in dbt.
The time spine supports Snowflake; decimal amounts retain their fractional part.

Deploy the semantic models in a dbt Semantic Layer environment. Then connect
Decision Layer with its GraphQL URL, environment ID and API token, following the
[dbt guide](../../../docs/guides/dbt.md). A successful data upload alone does not
prove that dbt deployment or the hosted API adapter works.
