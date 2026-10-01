"""assess_device's M1 platform boundary: Cisco IOS is assessed end to end;
anything else raises a clear "not yet supported" error rather than silently
producing an empty/wrong assessment (G2)."""

from __future__ import annotations

import pytest

from nsca_engine.api import assess_device
from nsca_engine.tests.helpers import ASSESSED_AT, build_knowledge_base, make_artifact


def test_non_cisco_content_raises_not_implemented():
    kb = build_knowledge_base()
    juniper_like = (
        "set system services ssh protocol-version v2\n"
        "set system services ssh root-login deny\n"
        "set interfaces ge-0/0/0 unit 0 family inet address 10.0.0.1/24\n"
    )
    with pytest.raises(NotImplementedError):
        assess_device((make_artifact(juniper_like),), kb, ASSESSED_AT)


def test_empty_artifact_tuple_raises_value_error():
    kb = build_knowledge_base()
    with pytest.raises(ValueError):
        assess_device((), kb, ASSESSED_AT)
