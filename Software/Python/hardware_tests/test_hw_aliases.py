"""Fan aliases: set -> read back -> restore."""
from urllib.parse import quote

import pytest

from harness import assert_error

pytestmark = [pytest.mark.aliases, pytest.mark.requires("aliases")]


def test_alias_roundtrip(api, fan):
    original = api.get(f"/api/v0/alias/{fan}/get")["alias"]
    new_alias = f"HW Test {fan}"
    try:
        api.get(f"/api/v0/alias/{fan}/set?value={quote(new_alias)}")
        assert api.get(f"/api/v0/alias/{fan}/get") == {"fan_id": fan, "alias": new_alias}
        assert api.get("/api/v0/alias/all/get")[str(fan)] == new_alias
    finally:
        api.get(f"/api/v0/alias/{fan}/set?value={quote(original)}")
    assert api.get(f"/api/v0/alias/{fan}/get")["alias"] == original


def test_invalid_alias_is_rejected(api):
    before = api.get("/api/v0/alias/0/get")["alias"]
    assert_error(api.raw("/api/v0/alias/0/set?value=%3Cscript%3E"), "can only contain")
    assert api.get("/api/v0/alias/0/get")["alias"] == before


def test_alias_on_invalid_fan_index_is_rejected(api, invalid_fan_index):
    assert_error(api.raw(f"/api/v0/alias/{invalid_fan_index}/set?value=x"), "Invalid fan index")
