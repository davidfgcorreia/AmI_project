package com.example.amishopengine

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import kotlin.math.sqrt

/**
 * Reads rotation vector (heading) and linear acceleration (step detection)
 * from the device sensors. Fires a callback at ~10 Hz with:
 *   heading  — compass bearing in degrees [0, 360)
 *   steps    — steps accumulated since last callback
 *   dt       — seconds since last callback
 *
 * The callback is delivered on whichever thread the sensor handler runs on;
 * callers must marshal to the UI thread themselves.
 */
class ImuManager(context: Context) : SensorEventListener {

    private val sensorManager =
        context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

    private var onImu: ((heading: Double, steps: Int, dt: Double) -> Unit)? = null

    // Step detection state
    private var pendingSteps = 0
    private var lastStepMs = 0L

    // Push timing
    private var lastPushMs = 0L

    // Heading from rotation vector
    private val rotMatrix  = FloatArray(9)
    private val orientation = FloatArray(3)

    fun start(callback: (heading: Double, steps: Int, dt: Double) -> Unit) {
        onImu = callback
        sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
        } ?: run { android.util.Log.w(TAG, "No rotation vector sensor") }

        // Prefer hardware step detector (more reliable than manual peak detection)
        val stepDetector = sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR)
        if (stepDetector != null) {
            sensorManager.registerListener(this, stepDetector, SensorManager.SENSOR_DELAY_FASTEST)
            android.util.Log.i(TAG, "Using TYPE_STEP_DETECTOR")
        } else {
            // Fallback to manual peak detection on linear acceleration
            sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)?.let {
                sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_UI)
            } ?: run { android.util.Log.w(TAG, "No step or acceleration sensor") }
            android.util.Log.i(TAG, "Falling back to linear acceleration step detection")
        }
    }

    fun stop() {
        sensorManager.unregisterListener(this)
        onImu = null
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {

            Sensor.TYPE_STEP_DETECTOR -> {
                // Hardware step detector fires once per step
                pendingSteps++
            }

            Sensor.TYPE_LINEAR_ACCELERATION -> {
                // Fallback step detection when TYPE_STEP_DETECTOR is unavailable
                val mag = sqrt(
                    event.values[0] * event.values[0] +
                    event.values[1] * event.values[1] +
                    event.values[2] * event.values[2]
                )
                val now = System.currentTimeMillis()
                if (mag > 2.5f && now - lastStepMs > 300) {
                    pendingSteps++
                    lastStepMs = now
                }
            }

            Sensor.TYPE_ROTATION_VECTOR -> {
                SensorManager.getRotationMatrixFromVector(rotMatrix, event.values)
                SensorManager.getOrientation(rotMatrix, orientation)

                // orientation[0] = azimuth in radians, convert to [0, 360)
                val heading = Math.toDegrees(orientation[0].toDouble())
                    .let { if (it < 0) it + 360.0 else it }

                val now = System.currentTimeMillis()
                val dt = if (lastPushMs == 0L) 0.1 else (now - lastPushMs) / 1000.0

                // Throttle to ~10 Hz
                if (lastPushMs == 0L || dt >= 0.1) {
                    onImu?.invoke(heading, pendingSteps, dt.coerceIn(0.01, 1.0))
                    pendingSteps = 0
                    lastPushMs = now
                }
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    companion object {
        private const val TAG = "ImuManager"
    }
}
