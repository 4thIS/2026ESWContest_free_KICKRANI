from pi.policy import policy
from pi import config


def test_safe_roads_get_full_speed():
    assert policy("asphalt") == config.SPEED_SAFE_MPS
    assert policy("bike_path") == config.SPEED_SAFE_MPS


def test_caution_roads_get_reduced_speed():
    assert policy("sidewalk_block") == config.SPEED_CAUTION_MPS
    assert policy("concrete") == config.SPEED_CAUTION_MPS


def test_gravel_gets_danger_speed():
    assert policy("gravel") == config.SPEED_DANGER_MPS


def test_unknown_road_fails_safe_to_danger_speed():
    assert policy("???") == config.SPEED_DANGER_MPS
