"""하드웨어 추상화 백엔드 — MockGpio 및 자동 선택."""
from pi.hardware.backend import MockGpio, get_gpio


def test_mock_records_output_writes():
    g = MockGpio()
    g.setup_output(5)
    g.write(5, 1)
    assert g.pin_state(5) == 1
    g.write(5, 0)
    assert g.pin_state(5) == 0


def test_mock_records_pwm_duty():
    g = MockGpio()
    g.setup_output(12)
    g.set_pwm(12, freq_hz=1000, duty=0.75)
    assert g.pwm_duty(12) == 0.75


def test_mock_input_read_defaults_low():
    g = MockGpio()
    g.setup_input(23)
    assert g.read(23) == 0


def test_mock_edge_callback_fires_on_pulse():
    g = MockGpio()
    g.setup_input(23)
    hits = []
    g.add_edge_callback(23, lambda: hits.append(1))
    g.simulate_pulse(23)
    g.simulate_pulse(23)
    assert len(hits) == 2


def test_get_gpio_returns_mock_when_not_on_pi():
    # 개발 PC(현재)에서는 lgpio가 없거나 Pi가 아니므로 MockGpio 반환.
    g = get_gpio(force_mock=True)
    assert isinstance(g, MockGpio)
