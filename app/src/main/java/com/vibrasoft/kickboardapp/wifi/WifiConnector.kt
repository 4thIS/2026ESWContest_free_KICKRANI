package com.vibrasoft.kickboardapp.wifi

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiNetworkSpecifier

class WifiConnector(context: Context) {
    private val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    fun connect(ssid: String, password: String, onResult: (Boolean) -> Unit) {
        disconnect()

        val specBuilder = WifiNetworkSpecifier.Builder().setSsid(ssid)
        if (password.isNotEmpty()) specBuilder.setWpa2Passphrase(password)

        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .setNetworkSpecifier(specBuilder.build())
            .build()

        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                cm.bindProcessToNetwork(network)
                onResult(true)
            }
            override fun onUnavailable() {
                onResult(false)
            }
        }

        cm.requestNetwork(request, networkCallback!!)
    }

    fun disconnect() {
        networkCallback?.let {
            try { cm.unregisterNetworkCallback(it) } catch (_: Exception) {}
        }
        networkCallback = null
        cm.bindProcessToNetwork(null)
    }
}
