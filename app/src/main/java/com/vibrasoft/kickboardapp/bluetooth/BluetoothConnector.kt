package com.vibrasoft.kickboardapp.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.util.UUID

class BluetoothConnector(context: Context) {
    private val adapter: BluetoothAdapter? =
        (context.applicationContext.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter

    private var socket: BluetoothSocket? = null
    private var reader: BufferedReader? = null

    companion object {
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    @SuppressLint("MissingPermission")
    fun pairedDevices(): List<BluetoothDevice> =
        adapter?.bondedDevices?.toList() ?: emptyList()

    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice): Boolean = withContext(Dispatchers.IO) {
        disconnect()
        try {
            val newSocket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            newSocket.connect()
            socket = newSocket
            reader = BufferedReader(InputStreamReader(newSocket.inputStream))
            true
        } catch (e: IOException) {
            false
        }
    }

    fun isConnected(): Boolean = socket?.isConnected == true

    suspend fun send(message: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val out = socket?.outputStream ?: return@withContext false
            out.write((message + "\n").toByteArray())
            out.flush()
            true
        } catch (e: IOException) {
            false
        }
    }

    suspend fun readLine(): String? = withContext(Dispatchers.IO) {
        try {
            reader?.readLine()
        } catch (e: IOException) {
            null
        }
    }

    fun disconnect() {
        try {
            socket?.close()
        } catch (e: IOException) {
            // ignore
        }
        socket = null
        reader = null
    }
}
