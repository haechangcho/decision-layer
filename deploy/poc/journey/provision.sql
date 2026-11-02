-- One-time provisioning by a PostgreSQL administrator with CREATEDB and CREATEROLE.
-- All object names are specific to the Decision Layer sample. No existing object
-- is modified or reused. CREATE DATABASE cannot run inside a transaction.
\set ON_ERROR_STOP on
\getenv loader_password DL_POC_LOADER_PASSWORD
\getenv reader_password DL_POC_READER_PASSWORD

-- Both values must be long and distinct. An unset variable also stops psql.
SELECT 1 / ((length(:'loader_password') >= 32 AND length(:'reader_password') >= 32
             AND :'loader_password' <> :'reader_password')::integer) AS passwords_valid;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_user
                 AND (rolsuper OR (rolcreatedb AND rolcreaterole))) THEN
    RAISE EXCEPTION 'The provisioning account requires CREATEDB and CREATEROLE.';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_database WHERE datname = 'dl_demo_journey') OR
     EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('dl_demo_loader', 'dl_demo_reader')) THEN
    RAISE EXCEPTION 'A PoC database or role name already exists; inspect it before proceeding.';
  END IF;
END $$;

CREATE ROLE dl_demo_loader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD :'loader_password';
CREATE ROLE dl_demo_reader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS PASSWORD :'reader_password';
CREATE DATABASE dl_demo_journey OWNER dl_demo_loader;
REVOKE ALL ON DATABASE dl_demo_journey FROM PUBLIC;
GRANT CONNECT ON DATABASE dl_demo_journey TO dl_demo_reader;

-- The dedicated loader revokes public schema creation after connecting to its DB.
