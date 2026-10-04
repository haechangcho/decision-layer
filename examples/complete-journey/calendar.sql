-- Keep source day indices intact; this fixed example calendar is not a purchase-year claim.
ALTER TABLE journey.transaction_data
  ADD COLUMN IF NOT EXISTS transaction_date date
  GENERATED ALWAYS AS (DATE '2000-01-01' + (day::integer - 1)) STORED;
ALTER TABLE journey.coupon_redempt
  ADD COLUMN IF NOT EXISTS redemption_date date
  GENERATED ALWAYS AS (DATE '2000-01-01' + (day::integer - 1)) STORED;
ALTER TABLE journey.campaign_desc
  ADD COLUMN IF NOT EXISTS start_date date
  GENERATED ALWAYS AS (DATE '2000-01-01' + (start_day::integer - 1)) STORED,
  ADD COLUMN IF NOT EXISTS end_date date
  GENERATED ALWAYS AS (DATE '2000-01-01' + (end_day::integer - 1)) STORED;

CREATE INDEX IF NOT EXISTS transaction_date_index ON journey.transaction_data(transaction_date);
CREATE INDEX IF NOT EXISTS redemption_date_index ON journey.coupon_redempt(redemption_date);
CREATE INDEX IF NOT EXISTS campaign_start_date_index ON journey.campaign_desc(start_date);
CREATE INDEX IF NOT EXISTS campaign_end_date_index ON journey.campaign_desc(end_date);
