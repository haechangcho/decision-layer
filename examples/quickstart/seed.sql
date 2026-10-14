-- Synthetic tutorial data, authored for this repository; not customer observations.
CREATE TABLE sales (id serial PRIMARY KEY, sold_at timestamp NOT NULL,
  department text NOT NULL, region text NOT NULL, revenue numeric NOT NULL);
INSERT INTO sales (sold_at, department, region, revenue)
SELECT d, department, region,
  CASE WHEN extract(month FROM d)=1 THEN CASE WHEN department='Home' THEN 200 ELSE 100 END
       WHEN extract(month FROM d)=2 THEN CASE WHEN department='Home' THEN 80 ELSE 240 END
       ELSE 120 END * CASE WHEN region='North' THEN 0.6 ELSE 0.4 END
FROM generate_series('2026-01-01'::timestamp, '2026-03-31', '1 day') d
CROSS JOIN (VALUES ('Home'), ('Grocery')) departments(department)
CROSS JOIN (VALUES ('North'), ('South')) regions(region);
CREATE USER demo_reader WITH PASSWORD 'local-demo-read-only';
GRANT CONNECT ON DATABASE demo TO demo_reader;
GRANT USAGE ON SCHEMA public TO demo_reader;
GRANT SELECT ON sales TO demo_reader;
