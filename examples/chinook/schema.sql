CREATE SCHEMA chinook;

CREATE TABLE chinook.genre (
    genre_id integer PRIMARY KEY,
    name text
);
CREATE TABLE chinook.media_type (
    media_type_id integer PRIMARY KEY,
    name text
);
CREATE TABLE chinook.artist (
    artist_id integer PRIMARY KEY,
    name text
);
CREATE TABLE chinook.album (
    album_id integer PRIMARY KEY,
    title text NOT NULL,
    artist_id integer NOT NULL REFERENCES chinook.artist
);
CREATE TABLE chinook.track (
    track_id integer PRIMARY KEY,
    name text NOT NULL,
    album_id integer REFERENCES chinook.album,
    media_type_id integer NOT NULL REFERENCES chinook.media_type,
    genre_id integer REFERENCES chinook.genre,
    composer text,
    milliseconds integer NOT NULL,
    bytes bigint,
    unit_price numeric(10,2) NOT NULL
);
CREATE TABLE chinook.employee (
    employee_id integer PRIMARY KEY,
    last_name text NOT NULL,
    first_name text NOT NULL,
    title text,
    reports_to integer REFERENCES chinook.employee DEFERRABLE INITIALLY DEFERRED,
    birth_date timestamp,
    hire_date timestamp,
    address text,
    city text,
    state text,
    country text,
    postal_code text,
    phone text,
    fax text,
    email text
);
CREATE TABLE chinook.customer (
    customer_id integer PRIMARY KEY,
    first_name text NOT NULL,
    last_name text NOT NULL,
    company text,
    address text,
    city text,
    state text,
    country text,
    postal_code text,
    phone text,
    fax text,
    email text NOT NULL,
    support_rep_id integer REFERENCES chinook.employee
);
CREATE TABLE chinook.invoice (
    invoice_id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES chinook.customer,
    invoice_date timestamp NOT NULL,
    billing_address text,
    billing_city text,
    billing_state text,
    billing_country text,
    billing_postal_code text,
    total numeric(10,2) NOT NULL
);
CREATE TABLE chinook.invoice_line (
    invoice_line_id integer PRIMARY KEY,
    invoice_id integer NOT NULL REFERENCES chinook.invoice,
    track_id integer NOT NULL REFERENCES chinook.track,
    unit_price numeric(10,2) NOT NULL,
    quantity integer NOT NULL
);
CREATE TABLE chinook.playlist (
    playlist_id integer PRIMARY KEY,
    name text
);
CREATE TABLE chinook.playlist_track (
    playlist_id integer REFERENCES chinook.playlist,
    track_id integer REFERENCES chinook.track,
    PRIMARY KEY (playlist_id, track_id)
);

CREATE INDEX ON chinook.invoice (invoice_date);
CREATE INDEX ON chinook.invoice (customer_id);
CREATE INDEX ON chinook.invoice_line (invoice_id);
CREATE INDEX ON chinook.invoice_line (track_id);
CREATE INDEX ON chinook.track (genre_id);
CREATE INDEX ON chinook.track (album_id);

CREATE SCHEMA IF NOT EXISTS demo_meta;
CREATE TABLE IF NOT EXISTS demo_meta.imports (
    dataset text PRIMARY KEY,
    source_sha256 text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
