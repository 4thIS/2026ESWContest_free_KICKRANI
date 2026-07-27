"""PID 컨트롤러 — 순수 로직, 하드웨어/시간 무관."""
from pi.motion.pid import PID


def test_proportional_only_output():
    # Kp=2, 오차=목표-측정=10-4=6 → 출력 12
    pid = PID(kp=2.0, ki=0.0, kd=0.0)
    out = pid.update(target=10.0, measured=4.0, dt=0.1)
    assert out == 12.0


def test_zero_error_gives_zero_output_without_integral():
    pid = PID(kp=1.0, ki=0.0, kd=0.0)
    assert pid.update(target=5.0, measured=5.0, dt=0.1) == 0.0


def test_integral_accumulates_over_time():
    # Ki=1, 오차 2 유지, dt=0.5 두 번 → 적분항 = 2*0.5 + 2*0.5 = 2.0
    pid = PID(kp=0.0, ki=1.0, kd=0.0)
    pid.update(target=2.0, measured=0.0, dt=0.5)
    out = pid.update(target=2.0, measured=0.0, dt=0.5)
    assert out == 2.0


def test_derivative_no_kick_on_first_sample():
    # 첫 호출엔 이전 오차가 없으므로 미분항=0 (기동 시 미분 킥 방지).
    # 두번째: 이전오차6(10-4), 현재오차2(10-8) → 미분(2-6)/0.1=-40
    pid = PID(kp=0.0, ki=0.0, kd=1.0)
    first = pid.update(target=10.0, measured=4.0, dt=0.1)
    second = pid.update(target=10.0, measured=8.0, dt=0.1)
    assert first == 0.0
    assert second == -40.0


def test_output_clamped_to_limits():
    pid = PID(kp=100.0, ki=0.0, kd=0.0, out_min=0.0, out_max=1.0)
    # 큰 오차여도 상한 1.0
    assert pid.update(target=10.0, measured=0.0, dt=0.1) == 1.0


def test_anti_windup_stops_integral_when_saturated():
    # 출력이 상한에 걸린 동안 적분이 무한정 쌓이지 않아야 함.
    pid = PID(kp=0.0, ki=10.0, kd=0.0, out_min=0.0, out_max=1.0)
    for _ in range(100):
        pid.update(target=1.0, measured=0.0, dt=0.1)
    # 목표에 도달(측정=목표)하면 즉시 감속 방향으로 빠져나올 수 있어야 함
    out = pid.update(target=1.0, measured=2.0, dt=0.1)  # 이제 오차 음수
    assert out < 1.0


def test_reset_clears_state():
    pid = PID(kp=0.0, ki=1.0, kd=0.0)
    pid.update(target=5.0, measured=0.0, dt=1.0)  # 적분 5 쌓임
    pid.reset()
    out = pid.update(target=0.0, measured=0.0, dt=1.0)
    assert out == 0.0


def test_pid_converges_to_setpoint_in_first_order_plant():
    """1차 관성 플랜트에 PID를 물려 목표 속도에 수렴하는지 검증."""
    from pi.config import PID_KP, PID_KI, PID_KD
    pid = PID(kp=PID_KP, ki=PID_KI, kd=PID_KD, out_min=0.0, out_max=1.0)
    target = 0.4
    speed = 0.0
    dt = 0.02
    k, tau = 1.0, 0.3  # 듀티 1.0 → 정상상태 속도 1.0 m/s, 시정수 0.3s
    for _ in range(1000):  # 20초 시뮬
        duty = pid.update(target=target, measured=speed, dt=dt)
        speed += (k * duty - speed) * dt / tau
    assert abs(speed - target) < 0.02  # 정상상태오차 2cm/s 이내
