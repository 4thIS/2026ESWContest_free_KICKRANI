package com.vibrasoft.kickboardapp.data

import android.content.Context

class AppSettings(context: Context) {
    private val prefs = context.getSharedPreferences("device_settings", Context.MODE_PRIVATE)

    var ssid: String
        get() = prefs.getString("ssid", "VibraSafe_AP") ?: "VibraSafe_AP"
        set(value) { prefs.edit().putString("ssid", value).apply() }

    var password: String
        get() = prefs.getString("password", "") ?: ""
        set(value) { prefs.edit().putString("password", value).apply() }

    var deviceIp: String
        get() = prefs.getString("device_ip", "192.168.4.1") ?: "192.168.4.1"
        set(value) { prefs.edit().putString("device_ip", value).apply() }

    var deviceAddress: String
        get() = prefs.getString("device_address", "") ?: ""
        set(value) { prefs.edit().putString("device_address", value).apply() }
}
