"""Each of the cloud's other fields (Details ▾) has a colour token of its own (owner,
2026-11-10: "colour customisation for optional metrics not working"); unset, it takes its
source's colour as before."""
import re

import franklinwh_ha_cloud_analytics as ca
from franklinwh_ha_cloud_analytics import payload

CSS = (ca.static_dir() / "cloud-analytics.css").read_text()


def test_every_detail_has_its_own_token_falling_back_to_its_source():
    keys = {k for k, _, _ in payload._EXTRA_TOTALS} | {k for k, _ in payload._EXTRA_FLOWS}
    for k in keys:
        assert re.search(r"\.c-%s\{ --c: var\(--ca-%s, var\(--ca-\w+\)\); \}" % (k, k), CSS), k
    assert ".c-solar_to_home{ --c: var(--ca-solar_to_home, var(--ca-solar)); }" in CSS
