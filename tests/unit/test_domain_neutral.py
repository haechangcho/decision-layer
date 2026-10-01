"""The core ships as open source: no example-domain vocabulary in src/.

Domain content (recipes, eval scenarios, expected values) belongs in examples/ and tests/.
"""
import re
from pathlib import Path

SRC = Path(__file__).parents[2] / "src"
# words of the bundled ecommerce example; extend when adding another example domain
EXAMPLE_TERMS = re.compile(
    r"ecom_|return_rate|반품|무료배송|택배|배송|매출|주문|객단가|카테고리|판매자|쿠폰|할인|환불|S017|여성의류"
    r"|free.?shipping|carrier|seller|refund|delivery",
    re.IGNORECASE)


def test_core_has_no_example_domain_terms():
    hits = [f"{p.relative_to(SRC)}:{i}: {line.strip()[:80]}"
            for p in SRC.rglob("*.py") for i, line in enumerate(p.read_text().splitlines(), 1)
            if EXAMPLE_TERMS.search(line)]
    assert not hits, "example-domain terms in core:\n" + "\n".join(hits)
