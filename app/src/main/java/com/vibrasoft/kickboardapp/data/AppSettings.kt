package com.vibrasoft.kickboardapp.data

import android.content.Context

class AppSettings(context: Context) {
    private val prefs = context.getSharedPreferences("device_settings", Context.MODE_PRIVATE)

    var deviceAddress: String
        get() = prefs.getString("device_address", "") ?: ""
        set(value) { prefs.edit().putString("device_address", value).apply() }
}
