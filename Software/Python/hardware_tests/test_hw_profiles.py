"""Fan profiles: add -> list -> apply (fans react) -> remove."""
from urllib.parse import quote

import pytest

pytestmark = [pytest.mark.profiles, pytest.mark.requires("profiles")]

PROFILE_LOW = "HW Test Low"
PROFILE_HIGH = "HW Test High"


@pytest.fixture
def cleanup_profiles(api, device):
    yield
    if device.has("profiles"):
        for name in (PROFILE_LOW, PROFILE_HIGH):
            api.raw(f"/api/v0/profiles/remove?name={quote(name)}")


def add_profile(api, name, pwm):
    return api.raw("/api/v0/profiles/add", method="POST",
                   data={"name": name, "type": "pwm", "values": ";".join([str(pwm)] * 10)})


def profile_names(api):
    return {p["name"] for p in api.get("/api/v0/profiles/list")}


def test_list_profiles(api, expect):
    reply = api.raw("/api/v0/profiles/list")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok"
    assert isinstance(reply["data"], list)


def test_add_and_remove_profile(api, device, expect, cleanup_profiles):
    reply = add_profile(api, PROFILE_LOW, 40)
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "ok", reply
    assert PROFILE_LOW in profile_names(api)

    api.get(f"/api/v0/profiles/remove?name={quote(PROFILE_LOW)}")
    assert PROFILE_LOW not in profile_names(api)


def test_applying_profiles_changes_fan_speed(api, device, wait, expect, cleanup_profiles):
    if expect.unsupported:
        expect.unsupported_error(api.raw(f"/api/v0/profiles/set?name={quote(PROFILE_LOW)}"))
        return
    if not device.fans_connected:
        pytest.skip(f"no fans connected on {device.name}")
    assert add_profile(api, PROFILE_LOW, 30)["status"] == "ok"
    assert add_profile(api, PROFILE_HIGH, 100)["status"] == "ok"

    api.get(f"/api/v0/profiles/set?name={quote(PROFILE_LOW)}")
    fan = device.fans_connected[0]
    wait(lambda: api.fan_rpm(fan) > 0, f"fan {fan} not spinning with the low profile")
    low = api.fan_rpm(fan)

    api.get(f"/api/v0/profiles/set?name={quote(PROFILE_HIGH)}")
    wait(lambda: api.fan_rpm(fan) > low * 1.1, f"fan {fan} did not speed up after applying the high profile")


def test_unknown_profile_is_rejected(api, expect):
    reply = api.raw("/api/v0/profiles/set?name=Does%20Not%20Exist")
    if expect.unsupported:
        expect.unsupported_error(reply)
        return
    assert reply["status"] == "error"
    assert "does not exist" in reply["message"]
