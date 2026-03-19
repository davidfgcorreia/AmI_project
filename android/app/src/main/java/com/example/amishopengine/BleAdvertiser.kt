package com.example.amishopengine

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.Context
import android.os.ParcelUuid
import android.util.Log

class BleAdvertiser(private val context: Context) {

    private var advertiser: BluetoothLeAdvertiser? = null
    private var callback: AdvertiseCallback? = null
    private var originalName: String? = null

    @SuppressLint("MissingPermission")
    fun start(sessionId: String) {
        val adapter = (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)
            ?.adapter

        if (adapter == null) {
            Log.e(TAG, "Bluetooth not available on this device")
            return
        }

        if (!adapter.isEnabled) {
            Log.e(TAG, "Bluetooth is off")
            return
        }

        advertiser = adapter.bluetoothLeAdvertiser
        if (advertiser == null) {
            Log.e(TAG, "Device does not support BLE peripheral mode")
            return
        }

        // Temporarily rename to session_id so ESP32 can read it via device.getName().
        // We restore the original name in stop().
        originalName = adapter.name
        adapter.setName(sessionId.take(18))

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
            .setConnectable(false)
            .setTimeout(0)
            .build()

        // Main advertisement: include the IRE service UUID so ESP32 can filter
        // and only process our app's packets, ignoring all other BLE devices
        val advertiseData = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .setIncludeTxPowerLevel(false)
            .addServiceUuid(ParcelUuid.fromString(IRE_SERVICE_UUID))
            .build()

        // Scan response: include device name (= session_id)
        // ESP32 uses setActiveScan(true) so it sends SCAN_REQ and gets this back
        val scanResponse = AdvertiseData.Builder()
            .setIncludeDeviceName(true)
            .build()

        callback = object : AdvertiseCallback() {
            override fun onStartSuccess(settingsInEffect: AdvertiseSettings) {
                Log.i(TAG, "Advertising started: $sessionId")
            }
            override fun onStartFailure(errorCode: Int) {
                Log.e(TAG, "Advertising failed, error code: $errorCode")
            }
        }

        advertiser?.startAdvertising(settings, advertiseData, scanResponse, callback!!)
    }

    @SuppressLint("MissingPermission")
    fun stop() {
        callback?.let { advertiser?.stopAdvertising(it) }
        // Restore the original Bluetooth device name
        originalName?.let {
            val adapter = (context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)
                ?.adapter
            adapter?.setName(it)
        }
        Log.i(TAG, "Advertising stopped, name restored to: $originalName")
    }

    companion object {
        private const val TAG = "BleAdvertiser"
        // Must match IRE_SERVICE_UUID in esp32_gateway.ino
        const val IRE_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    }
}
