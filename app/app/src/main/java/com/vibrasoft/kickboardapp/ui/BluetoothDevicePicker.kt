package com.vibrasoft.kickboardapp.ui

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import com.vibrasoft.kickboardapp.bluetooth.BluetoothConnector

class BluetoothDevicePicker(
    private val fragment: Fragment,
    private val connectorProvider: () -> BluetoothConnector,
    private val onDeviceSelected: (BluetoothDevice) -> Unit
) {
    private val permissionLauncher = fragment.registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> if (granted) showDialog() }

    fun requestPick() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val granted = ContextCompat.checkSelfPermission(
                fragment.requireContext(), Manifest.permission.BLUETOOTH_CONNECT
            ) == PackageManager.PERMISSION_GRANTED
            if (granted) showDialog() else permissionLauncher.launch(Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            showDialog()
        }
    }

    @SuppressLint("MissingPermission")
    private fun showDialog() {
        val devices = connectorProvider().pairedDevices()
        if (devices.isEmpty()) return
        val names = devices.map { it.name ?: it.address }.toTypedArray()
        AlertDialog.Builder(fragment.requireContext())
            .setTitle("기기 선택")
            .setItems(names) { _, which -> onDeviceSelected(devices[which]) }
            .setNegativeButton("취소", null)
            .show()
    }
}
