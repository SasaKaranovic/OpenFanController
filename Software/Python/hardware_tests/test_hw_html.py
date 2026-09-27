"""The web page shows the right things for this board, in the right place."""
import pytest

pytestmark = pytest.mark.html


@pytest.fixture(scope="module")
def page(api):
    return api.html("/")


def test_title_contains_board_name(page, device):
    assert page.title.get_text(strip=True) == f"{device.board.name} - Karanovic Research"


def test_one_rpm_tile_per_fan(page, device):
    for i in range(device.board.fan_count):
        tile = page.select_one(f"#fan-{i}-name")
        assert tile is not None, f"fan tile #fan-{i}-name missing"
        assert tile.get_text(strip=True) == f"Fan #{i + 1}"
        assert page.select_one(f"#fan-{i}-rpm") is not None
    assert page.select_one(f"#fan-{device.board.fan_count}-name") is None, "more fan tiles than fans"


def test_fan_selector_lists_every_fan(page, device):
    options = page.select("#fan_index option")
    assert [o.get("value") for o in options] == [str(i) for i in range(device.board.fan_count)]


def test_sensor_tiles_match_board(page, device):
    tiles = page.select("[id^=sensor-][id$=-name]")
    if device.has("temperature"):
        assert [t.get("id") for t in tiles] == [f"sensor-{i}-name" for i in range(device.board.sensor_count)]
    else:
        assert tiles == [], "board has no sensors but the page shows sensor tiles"


def test_profile_selector_only_with_profile_support(page, device):
    assert (page.select_one("#available-fan-profiles") is not None) == device.has("profiles")


def test_fan_control_slider_range(page, device):
    slider = page.select_one("#fan_value")
    assert slider is not None
    assert slider.get("max") == ("3000" if device.has("rpm_control") else "100")


def test_footer_shows_board_and_build(page, api, device):
    build = api.get("/api/v0/info")["software"].rsplit("Build: ", 1)[-1]
    footer = page.select_one("footer") or page
    text = footer.get_text(" ", strip=True)
    assert device.board.name in text
    assert build in text
