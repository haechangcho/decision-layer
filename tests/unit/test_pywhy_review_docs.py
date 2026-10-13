"""Keep translated review examples and executable references aligned."""
from pathlib import Path
import re


def test_review_languages_share_examples_and_sections():
    root = Path(__file__).resolve().parents[2]
    en = (root / "docs/guides/pywhy-review.md").read_text()
    ko = (root / "docs/ko/guides/pywhy-review.md").read_text()
    assert re.findall(r"```[^\n]*\n(.*?)```", en, re.S) == re.findall(r"```[^\n]*\n(.*?)```", ko, re.S)
    assert re.findall(r"^<<< .*$", en, re.M) == re.findall(r"^<<< .*$", ko, re.M)
    assert re.findall(r"^## (\d+)\.", en, re.M) == re.findall(r"^## (\d+)\.", ko, re.M) == [str(i) for i in range(1,13)]
    for reference in re.findall(r"^<<< @/\.\./(.+)$", en, re.M):
        path, region = reference.split("#")
        source = (root / path).read_text()
        assert f"#region {region}" in source and f"#endregion {region}" in source
