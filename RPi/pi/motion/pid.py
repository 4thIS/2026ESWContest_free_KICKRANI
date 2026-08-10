"""정속 주행용 PID 컨트롤러.

순수 로직: 하드웨어·실제 시간에 의존하지 않는다. dt를 인자로 받아
단독으로 완전히 테스트 가능. anti-windup(적분 포화 방지) 포함.
"""


class PID:
    def __init__(self, kp, ki, kd, out_min=float("-inf"), out_max=float("inf")):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.out_min = out_min
        self.out_max = out_max
        self._integral = 0.0
        self._prev_error = 0.0
        self._has_prev = False

    def reset(self):
        """적분·미분 상태 초기화 (주행 시작/정지 시 호출)."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._has_prev = False

    def update(self, target, measured, dt):
        error = target - measured

        # 미분항: 첫 호출엔 이전 오차가 없으므로 0
        if self._has_prev:
            derivative = (error - self._prev_error) / dt
        else:
            derivative = 0.0

        # 적분항 후보 (anti-windup: 포화 시 롤백)
        integral_candidate = self._integral + error * dt

        p = self.kp * error
        i = self.ki * integral_candidate
        d = self.kd * derivative
        output = p + i + d

        # 출력 클램프 + anti-windup
        if output > self.out_max:
            output = self.out_max
            # 오차가 여전히 출력을 더 밀어올리는 방향이면 적분 누적 중단
            if error <= 0:
                self._integral = integral_candidate
        elif output < self.out_min:
            output = self.out_min
            if error >= 0:
                self._integral = integral_candidate
        else:
            self._integral = integral_candidate

        self._prev_error = error
        self._has_prev = True
        return output
