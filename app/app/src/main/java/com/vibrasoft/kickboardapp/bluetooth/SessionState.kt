package com.vibrasoft.kickboardapp.bluetooth

/**
 * 세션 실행 상태 — Pi의 ACK/ERROR 응답을 근거로만 전이한다.
 * (명령 전송 자체로는 상태를 바꾸지 않는다: START가 거부돼도
 * 앱이 "실행 중"으로 잘못 표시하던 탈동기화 방지)
 */
class SessionState {
    var isRunning = false
        private set
    var isPending = false
        private set

    fun startRequested() {
        isPending = true
    }

    fun stopRequested() {
        isPending = true
    }

    fun onAck(cmd: String, ok: Boolean) {
        when (cmd) {
            "START" -> {
                isPending = false
                if (ok) isRunning = true
            }
            "STOP" -> {
                isPending = false
                if (ok) isRunning = false
            }
        }
    }

    fun onError(cmd: String) {
        if (cmd == "START" || cmd == "STOP") isPending = false
    }

    fun onTimeout() {
        isPending = false
    }

    fun onDisconnected() {
        isRunning = false
        isPending = false
    }
}
