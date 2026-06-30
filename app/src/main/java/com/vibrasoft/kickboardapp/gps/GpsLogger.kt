package com.vibrasoft.kickboardapp.gps

import android.annotation.SuppressLint
import android.content.Context
import android.os.Looper
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.vibrasoft.kickboardapp.network.GpsPoint

class GpsLogger(context: Context) {
    private val fusedClient = LocationServices.getFusedLocationProviderClient(context)
    private val points = mutableListOf<GpsPoint>()
    private var callback: LocationCallback? = null

    var onSpeedUpdate: ((Float) -> Unit)? = null

    companion object {
        fun buildNewFileName(original: String, roadType: String, condition: String): String {
            val base = original.removeSuffix(".csv")
            return "${base}_${roadType}_${condition}.csv"
        }
    }

    @SuppressLint("MissingPermission")
    fun start() {
        points.clear()
        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 1000L)
            .setMinUpdateIntervalMillis(1000L)
            .build()
        callback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val loc = result.lastLocation ?: return
                val speedKmh = loc.speed * 3.6f
                points.add(GpsPoint(System.currentTimeMillis(), speedKmh))
                onSpeedUpdate?.invoke(speedKmh)
            }
        }
        fusedClient.requestLocationUpdates(request, callback!!, Looper.getMainLooper())
    }

    fun stop(): List<GpsPoint> {
        callback?.let { fusedClient.removeLocationUpdates(it) }
        callback = null
        return points.toList().also { points.clear() }
    }
}
