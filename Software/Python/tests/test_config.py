"""Tests for `ConfigReader`: loading, defaults, and persisting `config.yaml`.

Every test works on a config file in pytest's temp directory, never the real `config.yaml`.
"""
import pytest
from ruamel import yaml

from config import ConfigReader


def read_yaml(path):
    with open(path, 'r', encoding="utf8") as file:
        return yaml.safe_load(file)


def write_yaml(path, data):
    with open(path, 'w', encoding="utf8") as file:
        yaml.dump(data, file, Dumper=yaml.RoundTripDumper)


def reload_config(path):
    """Simulate an application restart: drop in-memory state and read the file again."""
    return ConfigReader(path)


FULL_CONFIG = {
    'server': {'hostname': '0.0.0.0', 'port': 3131, 'communication_timeout': 2},
    'hardware': {'port': '/dev/ttyACM0', 'communication_timeout': 1},
    'fan_profiles': {'Quiet': {'type': 'pwm', 'values': [30] * 10}},
    'fan_aliases': {i: f'Alias {i}' for i in range(10)},
}


# --- Loading ---

def test_missing_file_uses_defaults_and_creates_it(config_path):
    cfg = ConfigReader(config_path)
    assert cfg.get_server_config() == {'hostname': 'localhost', 'port': 3000, 'communication_timeout': 1}
    assert cfg.get_hardware_config()['port'] == '__CHANGE_ME__'
    assert {'50% PWM', '100% PWM', '1000 RPM'} <= set(cfg.config['fan_profiles'])
    assert read_yaml(config_path)['server']['port'] == 3000


def test_empty_file_uses_defaults(config_path):
    open(config_path, 'w', encoding="utf8").close()
    cfg = ConfigReader(config_path)
    assert cfg.get_server_config()['port'] == 3000


def test_full_file_is_loaded(config_path):
    write_yaml(config_path, FULL_CONFIG)
    cfg = ConfigReader(config_path)
    assert cfg.get_server_config() == FULL_CONFIG['server']
    assert cfg.get_hardware_config() == FULL_CONFIG['hardware']
    assert cfg.get_fan_profile('Quiet') == {'type': 'pwm', 'values': [30] * 10}
    assert cfg.get_fan_alias(3) == 'Alias 3'


@pytest.mark.parametrize("missing_section", ['server', 'hardware', 'fan_profiles', 'fan_aliases'])
def test_missing_section_gets_default_and_is_saved(config_path, missing_section):
    partial = {k: v for k, v in FULL_CONFIG.items() if k != missing_section}
    write_yaml(config_path, partial)

    cfg = ConfigReader(config_path)
    defaults = {
        'server': ConfigReader.defualt_server,
        'hardware': ConfigReader.defualt_hardware,
        'fan_profiles': ConfigReader.default_fan_profiles,
        'fan_aliases': ConfigReader.default_fan_aliases,
    }
    assert cfg.config[missing_section] == defaults[missing_section]
    assert missing_section in read_yaml(config_path), "defaults should be written back to the file"


# --- Fan profiles ---

def test_update_fan_profile_persists(config, config_path):
    assert config.update_fan_profile('Silent', 'pwm', [20] * 10) is True
    assert config.get_fan_profile('Silent') == {'type': 'PWM', 'values': [20] * 10}
    assert reload_config(config_path).get_fan_profile('Silent') == {'type': 'PWM', 'values': [20] * 10}


def test_update_fan_profile_accepts_rpm(config):
    assert config.update_fan_profile('Slow', 'rpm', [800] * 10) is True
    assert config.get_fan_profile('Slow')['type'] == 'RPM'


def test_update_fan_profile_rejects_unknown_type(config):
    assert config.update_fan_profile('Bad', 'voltage', [1] * 10) is False
    assert config.get_fan_profile('Bad') is False


@pytest.mark.parametrize("count", [0, 9, 11])
def test_update_fan_profile_requires_ten_values(config, count):
    assert config.update_fan_profile('Bad', 'pwm', [50] * count) is False


@pytest.mark.parametrize("profile_type", ['P', 'R', 'W', 'PW', '', None, 'PWMX'])
def test_update_fan_profile_rejects_partial_type(config, profile_type):
    assert config.update_fan_profile('Bad', profile_type, [50] * 10) is False


def test_remove_fan_profile(config):
    assert config.remove_fan_profile('50% PWM') is True
    assert config.get_fan_profile('50% PWM') is False
    assert config.remove_fan_profile('50% PWM') is False


def test_get_all_fan_profiles_includes_name(config):
    profiles = config.get_all_fan_profiles()
    assert {p['name'] for p in profiles} == {'50% PWM', '100% PWM', '1000 RPM'}


@pytest.mark.xfail(strict=True, reason="Known bug: get_all_fan_profiles() adds a 'name' key to the stored "
                                        "profiles, which then gets written to config.yaml")
def test_get_all_fan_profiles_does_not_modify_stored_profiles(config, config_path):
    config.get_all_fan_profiles()
    config.update_fan_profile('Other', 'pwm', [10] * 10)     # triggers a save
    assert 'name' not in read_yaml(config_path)['fan_profiles']['50% PWM']


# --- Fan aliases ---

def test_get_fan_alias_defaults(config):
    assert config.get_fan_alias(0) == 'Fan #1'
    assert config.get_fan_alias(9) == 'Fan #10'
    assert len(config.get_fan_alias()) == 10


def test_get_fan_alias_unknown_index_falls_back(config):
    assert config.get_fan_alias(42) == 'Fan #43'


def test_set_fan_alias_persists(config, config_path):
    assert config.set_fan_alias(2, 'CPU Intake') is True
    assert config.get_fan_alias(2) == 'CPU Intake'
    assert reload_config(config_path).get_fan_alias(2) == 'CPU Intake'


# --- Isolation ---

def test_instances_are_independent(tmp_path):
    first_path = str(tmp_path / "first.yaml")
    second_path = str(tmp_path / "second.yaml")
    write_yaml(first_path, FULL_CONFIG)

    first = ConfigReader(first_path)
    write_yaml(second_path, {**FULL_CONFIG, 'server': {'hostname': 'localhost', 'port': 4000,
                                                       'communication_timeout': 1}})
    ConfigReader(second_path)
    assert first.get_server_config()['port'] == 3131
