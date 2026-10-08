"""Create an isolated dbt trial identity with an encrypted local key pair."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from copy_sample import TABLES, identifier


def statements(database: str, warehouse: str, public_key: str) -> list[str]:
    database, warehouse = identifier(database), identifier(warehouse)
    # The DER public key is base64, never user-authored SQL or a private credential.
    import base64
    base64.b64decode(public_key, validate=True)
    role = "DL_DBT_TEST_ROLE"
    return [
        f"CREATE SCHEMA IF NOT EXISTS {database}.ANALYTICS",
        f"CREATE ROLE {role}",
        f"GRANT USAGE ON DATABASE {database} TO ROLE {role}",
        f"GRANT USAGE ON WAREHOUSE {warehouse} TO ROLE {role}",
        f"GRANT USAGE ON SCHEMA {database}.JOURNEY TO ROLE {role}",
        *[f"GRANT SELECT ON TABLE {database}.JOURNEY.{identifier(table)} TO ROLE {role}"
          for table in TABLES],
        f"GRANT USAGE ON SCHEMA {database}.ANALYTICS TO ROLE {role}",
        f"GRANT CREATE TABLE, CREATE VIEW ON SCHEMA {database}.ANALYTICS TO ROLE {role}",
        "CREATE USER DL_DBT_TEST TYPE=SERVICE "
        f"DEFAULT_ROLE={role} DEFAULT_WAREHOUSE={warehouse} "
        f"DEFAULT_NAMESPACE='{database}.ANALYTICS' RSA_PUBLIC_KEY='{public_key}'",
        f"GRANT ROLE {role} TO USER DL_DBT_TEST",
    ]


def main() -> None:
    import base64
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True)
    parser.add_argument("--admin-user", required=True)
    parser.add_argument("--database", default="DL_JOURNEY_TEST")
    parser.add_argument("--warehouse", default="DL_TEST_WH")
    parser.add_argument("--keys-directory", required=True, type=Path)
    args = parser.parse_args()
    database, warehouse = identifier(args.database), identifier(args.warehouse)
    folder = args.keys_directory.expanduser().resolve()
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    key_path = folder / "dbt-test.p8"
    if key_path.exists():
        parser.error("Key already exists; existing credentials are not overwritten.")
    phrase = getpass.getpass("New private-key passphrase (not saved): ")
    if len(phrase) < 16:
        parser.error("Use a private-key passphrase with at least 16 characters.")
    if phrase != getpass.getpass("Confirm private-key passphrase: "):
        parser.error("Passphrases do not match.")
    password = getpass.getpass("Snowflake administrator password (not saved): ")
    passcode = getpass.getpass("MFA code (Enter for push approval): ")
    with snowflake.connector.connect(
        account=args.account, user=args.admin_user, password=password, role="ACCOUNTADMIN",
        authenticator="username_password_mfa", client_request_mfa_token=False,
        **({"passcode": passcode} if passcode else {}),
        login_timeout=120,
    ) as connection, connection.cursor() as cursor:
        for query in ["SHOW USERS LIKE 'DL_DBT_TEST'", "SHOW ROLES LIKE 'DL_DBT_TEST_ROLE'"]:
            cursor.execute(query)
            if cursor.fetchall():
                raise ValueError("Test identity or role already exists; no credentials are changed.")
        cursor.execute(f"DESCRIBE SCHEMA {database}.JOURNEY")
        cursor.execute(f"DESCRIBE WAREHOUSE {warehouse}")
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = private_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(phrase.encode()),
        )
        public_key = base64.b64encode(private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
        )).decode()
        # Retain the encrypted key if Snowflake setup fails partway through.
        with os.fdopen(os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
            output.write(private_bytes)
        for query in statements(database, warehouse, public_key):
            cursor.execute(query)
    with snowflake.connector.connect(
        account=args.account, user="DL_DBT_TEST", authenticator="SNOWFLAKE_JWT",
        private_key=private_key.private_bytes(
            serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        role="DL_DBT_TEST_ROLE", database=database, schema="ANALYTICS", warehouse=warehouse,
        login_timeout=120, session_parameters={"STATEMENT_TIMEOUT_IN_SECONDS": 60},
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT CURRENT_ROLE()")
        if cursor.fetchone()[0] != "DL_DBT_TEST_ROLE":
            raise ValueError("Unexpected test execution role.")
        cursor.execute(f"CREATE TEMPORARY VIEW DBT_CONNECTION_CHECK AS "
                       f"SELECT HOUSEHOLD_KEY FROM {database}.JOURNEY.HOUSEHOLD")
        cursor.execute("SELECT COUNT(*) FROM DBT_CONNECTION_CHECK")
        print(f"Verified key-pair login, source read and view creation: {cursor.fetchone()[0]:,} households.")
    print("Created DL_DBT_TEST with DL_DBT_TEST_ROLE; no administrator role granted.")
    print(f"Encrypted private key: {key_path}")
    print(f"dbt connection: account={args.account}, database={database}, warehouse={warehouse}, schema=ANALYTICS")
    print("Keep the key and passphrase private. Enter them directly in dbt, not in chat or Git.")


if __name__ == "__main__":
    main()
