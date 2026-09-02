package com.vibrasoft.kickboardapp.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import android.util.Log
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
        private const val TAG = "RpiLink"
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    @SuppressLint("MissingPermission")
    fun pairedDevices(): List<BluetoothDevice> =
        adapter?.bondedDevices?.toList() ?: emptyList()

    @SuppressLint("MissingPermission")
    suspend fun connect(device: BluetoothDevice): Boolean = withContext(Dispatchers.IO) {
        disconnect()
        Log.i(TAG, "connect 시도: ${device.address} uuid=$SPP_UUID")
        try {
            val newSocket = device.createRfcommSocketToServiceRecord(SPP_UUID)
            newSocket.connect()
            socket = newSocket
            reader = BufferedReader(InputStreamReader(newSocket.inputStream))
            Log.i(TAG, "connect 성공: ${device.address}")
            true
        } catch (e: IOException) {
            // SDP에 SPP 레코드 없음(rfcomm_setup.sh 미실행)·페어링 해제·서버 미기동 등이 여기로 온다
            Log.e(TAG, "connect 실패: ${device.address} — ${e.javaClass.simpleName}: ${e.message}")
            false
        }
    }

    fun isConnected(): Boolean = socket?.isConnected == true

    suspend fun send(message: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val out = socket?.outputStream ?: run {
                Log.w(TAG, "send 실패: 소켓 없음 — $message")
                return@withContext false
            }
            out.write((message + "\n").toByteArray())
            out.flush()
            Log.d(TAG, "→ $message")
            true
        } catch (e: IOException) {
            Log.e(TAG, "send 실패: ${e.javaClass.simpleName}: ${e.message} — $message")
            false
        }
    }

    suspend fun readLine(): String? = withContext(Dispatchers.IO) {
        try {
            val line = reader?.readLine()
            if (line == null) Log.w(TAG, "readLine null — 스트림 종료(끊김)") else Log.d(TAG, "← $line")
            line
        } catch (e: IOException) {
            Log.e(TAG, "readLine 실패: ${e.javaClass.simpleName}: ${e.message}")
            null
        }
    }

    fun disconnect() {
        if (socket != null) Log.i(TAG, "disconnect")
        try {
            socket?.close()
        } catch (e: IOException) {
            Log.w(TAG, "소켓 close 실패: ${e.message}")
        }
        socket = null
        reader = null
    }
}
