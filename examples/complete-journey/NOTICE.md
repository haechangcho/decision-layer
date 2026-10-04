# Source and interpretation

Data: dunnhumby, The Complete Journey, official source-files archive (2023 packaging).
Source: https://www.dunnhumby.com/source-files/
Reference example: https://www.databricks.com/notebooks/segment-p13n/sg_01_data_prep.html

The source data and its user guide remain copyright dunnhumby, all rights reserved.
Decision Layer ships an original loader and semantic model, not the data or Databricks notebook code.
The archive is downloaded directly from the publisher at runtime. Public availability is not an Apache license grant.
Review the publisher's terms for your intended use; obtain permission before mirroring or redistributing the data.

SHA-256: 5e0a3d72fe8562fe0ab995f70fb58b74359e8ec4bbccd1521e2b137da0558f9a

The current official archive uses coded demographic classifications. We preserve these codes,
rather than label them with age or income bands from an older dataset version.
Source DAY is a relative index. The importer retains it and adds PostgreSQL DATE columns,
mapping day 1 to 2000-01-01 with a fixed example calendar. Cube references those columns.
These are artificial dates, not actual purchase dates; campaign and redemption dates use the same mapping.
SALES_VALUE is retailer receipts, not necessarily customer cash paid or profit.
Coupon redemption is not a purchase-line attribution, and campaign targeting is not randomized assignment.
No known causal ground truth is supplied. The name causal_data denotes promotion placement information,
not proof of causal identification.
