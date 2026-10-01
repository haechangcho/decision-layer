-- Synthetic ecommerce data (schema ecom) for developing and testing Decision Layer.
-- Not real data. setseed() fixes the random numbers, so everyone gets identical rows.
-- Loaded once by the example's postgres container on an empty volume.
--
-- Planted effects and the answers they should produce: ../EXPECTED.md.
-- If you change the generation rules, update that file too.

\c sampledb

-- 병렬 실행 시 random() 호출 순서가 달라져 결과가 바뀌므로 끈다.
SET max_parallel_workers_per_gather = 0;

DROP SCHEMA IF EXISTS ecom CASCADE;
CREATE SCHEMA ecom;

SELECT setseed(0.2026);

-- ── 카테고리 ────────────────────────────────────────────────────────────────
CREATE TABLE ecom.dim_category (
    category_id  varchar(10) PRIMARY KEY,
    category_l1  varchar(20) NOT NULL,
    category_nm  varchar(30) NOT NULL,
    base_price   integer     NOT NULL
);

-- 기준 반품 확률은 생성 전용이라 공개 테이블에 두지 않는다.
CREATE TEMP TABLE t_category_effect (category_id varchar(10) PRIMARY KEY, base_return numeric);

INSERT INTO ecom.dim_category VALUES
    ('CT01', '패션', '여성의류',       45000),
    ('CT02', '패션', '남성의류',       40000),
    ('CT03', '패션', '신발',           70000),
    ('CT04', '뷰티', '스킨케어',       30000),
    ('CT05', '뷰티', '메이크업',       20000),
    ('CT06', '가전', '소형가전',      120000),
    ('CT07', '가전', '모바일액세서리', 25000),
    ('CT08', '가전', '생활가전',      350000),
    ('CT09', '식품', '신선식품',       30000),
    ('CT10', '식품', '가공식품',       20000),
    ('CT11', '리빙', '가구',          250000),
    ('CT12', '리빙', '주방용품',       35000);

INSERT INTO t_category_effect VALUES
    ('CT01', 0.14), ('CT02', 0.10), ('CT03', 0.12),
    ('CT04', 0.03), ('CT05', 0.04),
    ('CT06', 0.05), ('CT07', 0.06), ('CT08', 0.04),
    ('CT09', 0.03), ('CT10', 0.02),
    ('CT11', 0.07), ('CT12', 0.03);

-- ── 판매자 ──────────────────────────────────────────────────────────────────
-- S001~S020 패션MD1팀, S021~S040 패션MD2팀, 이후 20명씩 뷰티/가전/식품/리빙.
-- S015는 2026-07-01부터 패션MD2팀으로 이동했다(dim은 현재 소속, fact_order는 주문 시점 소속).
CREATE TABLE ecom.dim_seller (
    seller_id    varchar(10) PRIMARY KEY,
    seller_nm    varchar(30) NOT NULL,
    category_l1  varchar(20) NOT NULL,
    md_team_nm   varchar(20) NOT NULL,
    seller_grade varchar(10) NOT NULL,
    join_dt      date        NOT NULL
);

CREATE TEMP TABLE t_seller_effect (seller_id varchar(10) PRIMARY KEY, return_effect numeric);

INSERT INTO ecom.dim_seller
SELECT
    'S' || lpad(g::text, 3, '0'),
    '판매자' || lpad(g::text, 3, '0'),
    CASE WHEN g <= 40 THEN '패션' WHEN g <= 60 THEN '뷰티' WHEN g <= 80 THEN '가전'
         WHEN g <= 100 THEN '식품' ELSE '리빙' END,
    CASE WHEN g = 15 THEN '패션MD2팀'
         WHEN g <= 20 THEN '패션MD1팀' WHEN g <= 40 THEN '패션MD2팀' WHEN g <= 60 THEN '뷰티MD팀'
         WHEN g <= 80 THEN '가전MD팀' WHEN g <= 100 THEN '식품MD팀' ELSE '리빙MD팀' END,
    CASE WHEN r.r1 < 0.2 THEN '파워' WHEN r.r1 < 0.8 THEN '일반' ELSE '신규' END,
    DATE '2022-01-01' + floor(r.r2 * 1400)::int
FROM generate_series(1, 120) g
CROSS JOIN LATERAL (SELECT g AS _g, random() AS r1, random() AS r2) r;

INSERT INTO t_seller_effect
SELECT seller_id, (random() - 0.5) * 0.01 FROM ecom.dim_seller ORDER BY seller_id;

-- ── 상품 ────────────────────────────────────────────────────────────────────
CREATE TABLE ecom.dim_product (
    product_id  varchar(10) PRIMARY KEY,
    product_nm  varchar(40) NOT NULL,
    category_id varchar(10) NOT NULL REFERENCES ecom.dim_category,
    seller_id   varchar(10) NOT NULL REFERENCES ecom.dim_seller,
    list_price  integer     NOT NULL
);

CREATE TEMP TABLE t_product_base AS
SELECT
    g,
    1 + floor(r.r1 * 120)::int AS seller_no,
    r.r2 AS r_cat,
    -- Box-Muller 표준정규
    sqrt(-2 * ln(1 - r.r3)) * cos(2 * pi() * r.r4) AS z
FROM generate_series(1, 3000) g
CROSS JOIN LATERAL (SELECT g AS _g, random() AS r1, random() AS r2, random() AS r3, random() AS r4) r;

INSERT INTO ecom.dim_product
SELECT
    'P' || lpad(b.g::text, 4, '0'),
    c.category_nm || ' 상품 ' || b.g,
    c.category_id,
    s.seller_id,
    greatest(1000, round(c.base_price * exp(0.5 * b.z) / 100) * 100)::int
FROM t_product_base b
JOIN ecom.dim_seller s ON s.seller_id = 'S' || lpad(b.seller_no::text, 3, '0')
JOIN LATERAL (
    SELECT dc.*, row_number() OVER (ORDER BY dc.category_id) AS rn, count(*) OVER () AS cnt
    FROM ecom.dim_category dc WHERE dc.category_l1 = s.category_l1
) c ON c.rn = 1 + floor(b.r_cat * c.cnt)::int
ORDER BY b.g;

-- ── 고객 ────────────────────────────────────────────────────────────────────
CREATE TABLE ecom.dim_customer (
    customer_id  varchar(10) PRIMARY KEY,
    gender       varchar(5)  NOT NULL,
    age_band     varchar(10) NOT NULL,
    region       varchar(10) NOT NULL,
    member_grade varchar(10) NOT NULL,
    signup_dt    date        NOT NULL
);

INSERT INTO ecom.dim_customer
SELECT
    'C' || lpad(g::text, 6, '0'),
    CASE WHEN r.r1 < 0.58 THEN 'F' ELSE 'M' END,
    CASE WHEN r.r2 < 0.15 THEN '20대 미만' WHEN r.r2 < 0.40 THEN '20대' WHEN r.r2 < 0.65 THEN '30대'
         WHEN r.r2 < 0.85 THEN '40대' ELSE '50대 이상' END,
    CASE WHEN r.r3 < 0.30 THEN '서울' WHEN r.r3 < 0.55 THEN '경기' WHEN r.r3 < 0.80 THEN '광역시'
         WHEN r.r3 < 0.95 THEN '지방' ELSE '도서산간' END,
    CASE WHEN r.r4 < 0.55 THEN '일반' WHEN r.r4 < 0.80 THEN '실버' WHEN r.r4 < 0.95 THEN '골드' ELSE 'VIP' END,
    DATE '2020-01-01' + floor(r.r5 * 2190)::int
FROM generate_series(1, 40000) g
CROSS JOIN LATERAL (SELECT g AS _g, random() AS r1, random() AS r2, random() AS r3, random() AS r4, random() AS r5) r;

-- ── 주문 원천 난수 ──────────────────────────────────────────────────────────
-- 모든 난수를 먼저 한 번에 뽑고, 이후 단계는 결정적 규칙만 적용한다.
CREATE TEMP TABLE t_order_base AS
SELECT
    g,
    DATE '2026-01-01' + floor(r.r_dt * 273)::int AS order_dt,   -- 2026-01-01 ~ 2026-09-30
    1 + floor(power(r.r_prod, 1.6) * 3000)::int AS product_no, -- 인기 상품 쏠림
    1 + floor(r.r_cust * 40000)::int AS customer_no,
    r.*
FROM generate_series(1, 200000) g
CROSS JOIN LATERAL (
    SELECT g AS _g,
           random() AS r_dt, random() AS r_prod, random() AS r_cust, random() AS r_channel,
           random() AS r_qty, random() AS r_coupon, random() AS r_free, random() AS r_carrier,
           random() AS r_wh, random() AS r_late, random() AS r_late_days, random() AS r_ret,
           random() AS r_ret_days, random() AS r_partial, random() AS r_reason
) r;

-- ── 주문 ────────────────────────────────────────────────────────────────────
CREATE TABLE ecom.fact_order (
    order_id         varchar(12) PRIMARY KEY,
    order_dt         date        NOT NULL,
    customer_id      varchar(10) NOT NULL REFERENCES ecom.dim_customer,
    product_id       varchar(10) NOT NULL REFERENCES ecom.dim_product,
    seller_id        varchar(10) NOT NULL REFERENCES ecom.dim_seller,
    md_team_nm       varchar(20) NOT NULL,   -- 주문 시점의 판매자 소속 MD팀
    channel          varchar(20) NOT NULL,
    quantity         integer     NOT NULL,
    coupon_used      boolean     NOT NULL,
    is_free_shipping boolean     NOT NULL,
    order_amount     integer     NOT NULL
);

CREATE TEMP TABLE t_order AS
SELECT
    b.*,
    'O' || lpad(b.g::text, 7, '0') AS order_id,
    p.product_id, p.seller_id, p.category_id, c.category_l1,
    cu.customer_id, cu.region, cu.member_grade,
    CASE WHEN b.order_dt >= DATE '2026-09-01' AND c.category_l1 = '패션' AND b.r_channel < 0.06 THEN 'live_commerce'
         WHEN b.r_channel < 0.45 THEN 'app'
         WHEN b.r_channel < 0.70 THEN 'web'
         WHEN b.r_channel < 0.90 THEN 'mobile_web'
         ELSE 'marketplace' END AS channel,
    1 + floor(power(b.r_qty, 2) * 3)::int AS quantity,
    b.r_coupon < 0.30 AS coupon_used
FROM t_order_base b
JOIN ecom.dim_product  p  ON p.product_id  = 'P' || lpad(b.product_no::text, 4, '0')
JOIN ecom.dim_category c  ON c.category_id = p.category_id
JOIN ecom.dim_customer cu ON cu.customer_id = 'C' || lpad(b.customer_no::text, 6, '0');

ALTER TABLE t_order ADD COLUMN order_amount integer, ADD COLUMN is_free_shipping boolean;

UPDATE t_order o
SET order_amount = round(p.list_price * o.quantity * CASE WHEN o.coupon_used THEN 0.9 ELSE 1 END)::int
FROM ecom.dim_product p WHERE p.product_id = o.product_id;

-- 무료배송은 고가 주문·패션·앱 주문에 몰린다(교란). 반품률에 대한 실제 효과는 +1.5%p.
UPDATE t_order
SET is_free_shipping = r_free < least(0.95,
      0.10
    + CASE WHEN order_amount >= 50000 THEN 0.35 ELSE 0 END
    + CASE WHEN category_l1 = '패션' THEN 0.20 ELSE 0 END
    + CASE WHEN channel = 'app' THEN 0.10 ELSE 0 END);

INSERT INTO ecom.fact_order
SELECT
    order_id, order_dt, customer_id, product_id, seller_id,
    CASE WHEN seller_id = 'S015' AND order_dt < DATE '2026-07-01' THEN '패션MD1팀'
         ELSE (SELECT md_team_nm FROM ecom.dim_seller s WHERE s.seller_id = t_order.seller_id) END,
    channel, quantity, coupon_used, is_free_shipping, order_amount
FROM t_order
ORDER BY g;

-- ── 배송 ────────────────────────────────────────────────────────────────────
-- 택배사는 지역에 따라 배정된다(교란). 지연률에 대한 실제 효과: B택배 +2.0%p, C택배 0.
CREATE TABLE ecom.fact_delivery (
    order_id      varchar(12) PRIMARY KEY REFERENCES ecom.fact_order,
    carrier_nm    varchar(10) NOT NULL,
    warehouse_nm  varchar(10) NOT NULL,
    ship_dt       date        NOT NULL,
    promised_dt   date        NOT NULL,
    delivered_dt  date        NOT NULL,
    is_late       boolean     NOT NULL,
    delivery_days integer     NOT NULL
);

CREATE TEMP TABLE t_delivery AS
SELECT
    o.order_id, o.order_dt, o.r_late, o.r_late_days, o.region,
    CASE
        WHEN o.region = '도서산간' THEN CASE WHEN o.r_carrier < 0.70 THEN 'C택배' WHEN o.r_carrier < 0.85 THEN 'A택배' ELSE 'B택배' END
        WHEN o.region = '지방'     THEN CASE WHEN o.r_carrier < 0.40 THEN 'C택배' WHEN o.r_carrier < 0.75 THEN 'A택배' ELSE 'B택배' END
        ELSE                            CASE WHEN o.r_carrier < 0.20 THEN 'C택배' WHEN o.r_carrier < 0.65 THEN 'A택배' ELSE 'B택배' END
    END AS carrier_nm,
    CASE
        WHEN o.region IN ('서울', '경기') THEN '수도권센터'
        WHEN o.region = '광역시' THEN CASE WHEN o.r_wh < 0.5 THEN '남부센터' ELSE '중부센터' END
        WHEN o.region = '지방' THEN '중부센터'
        ELSE '남부센터'
    END AS warehouse_nm,
    o.order_dt + CASE WHEN o.region = '도서산간' THEN 4 ELSE 2 END AS promised_dt
FROM t_order o;

ALTER TABLE t_delivery ADD COLUMN is_late boolean;

UPDATE t_delivery
SET is_late = r_late < (
      CASE region WHEN '서울' THEN 0.03 WHEN '경기' THEN 0.04 WHEN '광역시' THEN 0.05
                  WHEN '지방' THEN 0.08 ELSE 0.25 END
    + CASE WHEN warehouse_nm = '남부센터' THEN 0.01 ELSE 0 END
    + CASE WHEN order_dt BETWEEN DATE '2026-09-20' AND DATE '2026-09-30' THEN 0.05 ELSE 0 END  -- 추석 물량
    + CASE WHEN carrier_nm = 'B택배' THEN 0.02 ELSE 0 END);

INSERT INTO ecom.fact_delivery
SELECT
    order_id, carrier_nm, warehouse_nm,
    order_dt + 1,
    promised_dt,
    CASE WHEN is_late THEN promised_dt + 1 + floor(r_late_days * 3)::int
         ELSE promised_dt - floor(r_late_days * 2)::int END,
    is_late,
    CASE WHEN is_late THEN promised_dt + 1 + floor(r_late_days * 3)::int
         ELSE promised_dt - floor(r_late_days * 2)::int END - order_dt
FROM t_delivery
ORDER BY order_id;

-- ── 반품 ────────────────────────────────────────────────────────────────────
-- 반품 확률은 모든 항이 더해지는 구조라 무료배송 효과가 모든 조건층에서 +1.5%p로 같다.
CREATE TABLE ecom.fact_return (
    order_id      varchar(12) PRIMARY KEY REFERENCES ecom.fact_order,
    return_dt     date        NOT NULL,
    return_reason varchar(20) NOT NULL,
    refund_amount integer     NOT NULL
);

INSERT INTO ecom.fact_return
SELECT
    o.order_id,
    d.delivered_dt + 1 + floor(o.r_ret_days * 7)::int,
    CASE WHEN d.is_late AND o.r_reason < 0.4 THEN '배송지연'
         WHEN o.category_l1 = '패션' AND o.r_reason < 0.6 THEN '사이즈'
         WHEN o.r_reason < 0.7 THEN '단순변심'
         WHEN o.r_reason < 0.9 THEN '상품불량'
         ELSE '오배송' END,
    CASE WHEN o.r_partial < 0.2 THEN round(o.order_amount * 0.5)::int ELSE o.order_amount END
FROM t_order o
JOIN ecom.fact_delivery d ON d.order_id = o.order_id
JOIN t_category_effect ce ON ce.category_id = o.category_id
JOIN t_seller_effect se ON se.seller_id = o.seller_id
WHERE o.r_ret < (
      ce.base_return
    + CASE o.channel WHEN 'marketplace' THEN 0.03 WHEN 'mobile_web' THEN 0.01
                     WHEN 'live_commerce' THEN 0.05 ELSE 0 END
    + CASE WHEN o.order_amount >= 300000 THEN 0.03 WHEN o.order_amount >= 100000 THEN 0.02
           WHEN o.order_amount >= 30000 THEN 0.01 ELSE 0 END
    + CASE WHEN o.is_free_shipping THEN 0.015 ELSE 0 END
    + se.return_effect
    + CASE WHEN o.member_grade = 'VIP' THEN -0.01 ELSE 0 END
    + CASE WHEN d.is_late THEN 0.03 ELSE 0 END
    + CASE WHEN o.seller_id = 'S017' AND o.category_id = 'CT01' THEN 0.08 ELSE 0 END)
ORDER BY o.order_id;

CREATE INDEX ix_fact_order_order_dt ON ecom.fact_order (order_dt);


ANALYZE ecom.dim_category, ecom.dim_seller, ecom.dim_product, ecom.dim_customer,
        ecom.fact_order, ecom.fact_delivery, ecom.fact_return;
