package com.vibrasoft.kickboardapp.data

enum class SpeedUnit { KMH, MPS }

object SpeedFormat {
    // 유선 값은 m/s 원값(공통계약 계약 2) — 환산은 표시 시점에만 한다
    fun format(speedMps: Float?, unit: SpeedUnit): String = when (unit) {
        SpeedUnit.KMH -> speedMps?.let { "%.1f km/h".format(it * 3.6f) } ?: "- km/h"
        SpeedUnit.MPS -> speedMps?.let { "%.1f m/s".format(it) } ?: "- m/s"
    }
}
