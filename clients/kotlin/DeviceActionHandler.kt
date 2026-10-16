package com.yarbis.client.handler

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.net.Uri
import android.provider.AlarmClock
import android.util.Base64
import android.util.Log
import com.yarbis.client.model.ActionType
import com.yarbis.client.model.YarbisResponse
import java.io.File
import java.io.FileOutputStream

/**
 * Manejador nativo en Android (Kotlin) para ejecutar las acciones de hardware
 * y reproducir el audio de respuesta generado por Yarbis.
 */
class DeviceActionHandler(
    private val context: Context,
    private val baseUrl: String = "http://10.0.2.2:8000"
) {
    companion object {
        private const val TAG = "DeviceActionHandler"
    }

    private var mediaPlayer: MediaPlayer? = null

    /**
     * Procesa la respuesta de Yarbis: reproduce el audio sintetizado, despacha la acción si corresponde
     * y notifica mediante onComplete cuando termina la reproducción de voz.
     */
    fun handleResponse(response: YarbisResponse, onComplete: (() -> Unit)? = null) {
        val hasAudio = !response.audioBase64.isNullOrEmpty() || !response.audioUrl.isNullOrEmpty()

        // 1. Reproducción de Audio (Base64 instantáneo o streaming por URL)
        if (hasAudio) {
            playAudioResponse(response, onComplete)
        } else {
            onComplete?.invoke()
        }

        // 2. Si no es control de dispositivo, no requiere acción nativa
        if (response.actionType != ActionType.DEVICE_CONTROL || response.command.isNullOrBlank()) {
            return
        }

        // 3. Despachar acción nativa de Android según el comando
        val params = response.parameters
        dispatchDeviceCommand(response.command, params)
    }

    private fun playAudioResponse(response: YarbisResponse, onComplete: (() -> Unit)? = null) {
        try {
            mediaPlayer?.release()
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                        .build()
                )
            }

            if (!response.audioBase64.isNullOrEmpty()) {
                // Reproducción directa desde Base64 (sin segunda petición HTTP)
                val audioBytes = Base64.decode(response.audioBase64, Base64.DEFAULT)
                val tempAudioFile = File.createTempFile("yarbis_tts_", ".mp3", context.cacheDir)
                FileOutputStream(tempAudioFile).use { it.write(audioBytes) }

                mediaPlayer?.apply {
                    setDataSource(tempAudioFile.absolutePath)
                    prepare()
                    start()
                    setOnCompletionListener {
                        tempAudioFile.delete()
                        onComplete?.invoke()
                    }
                    setOnErrorListener { _, _, _ ->
                        tempAudioFile.delete()
                        onComplete?.invoke()
                        false
                    }
                }
            } else if (!response.audioUrl.isNullOrEmpty()) {
                // Streaming o descarga por URL (absoluta o relativa con baseUrl)
                val fullUrl = if (response.audioUrl.startsWith("http")) {
                    response.audioUrl
                } else {
                    "${baseUrl.trimEnd('/')}${response.audioUrl}"
                }

                mediaPlayer?.apply {
                    setDataSource(fullUrl)
                    prepareAsync()
                    setOnPreparedListener { start() }
                    setOnCompletionListener {
                        onComplete?.invoke()
                    }
                    setOnErrorListener { _, _, _ ->
                        onComplete?.invoke()
                        false
                    }
                }
            } else {
                onComplete?.invoke()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reproduciendo audio: ${e.message}", e)
            onComplete?.invoke()
        }
    }

    private fun dispatchDeviceCommand(command: String, params: Map<String, Any?>) {
        when (command) {
            "toggle_flashlight" -> {
                val state = (params["state"] as? Boolean) ?: false
                setFlashlight(state)
            }

            "set_volume" -> {
                val percent = (params["level_percent"] as? Number)?.toInt() ?: 50
                setDeviceVolume(percent)
            }

            "set_alarm" -> {
                val time = params["time"] as? String ?: "08:00"
                val label = params["label"] as? String ?: "Alarma Yarbis"
                setAlarm(time, label)
            }

            "set_timer" -> {
                val duration = (params["duration_seconds"] as? Number)?.toInt() ?: 60
                val label = params["label"] as? String ?: "Temporizador Yarbis"
                setTimer(duration, label)
            }

            "open_app" -> {
                val appName = (params["app_name"] as? String) ?: ""
                val packageName = (params["package_name"] as? String)
                openApplication(appName, packageName)
            }

            "make_phone_call" -> {
                val phone = params["phone_number"] as? String
                if (!phone.isNullOrBlank()) {
                    makePhoneCall(phone)
                }
            }

            "send_message" -> {
                val recipient = params["recipient"] as? String ?: ""
                val message = params["message_body"] as? String ?: ""
                val app = params["app"] as? String ?: "whatsapp"
                sendMessage(recipient, message, app)
            }

            "play_media" -> {
                val query = (params["query"] as? String) ?: "música"
                val platform = ((params["platform"] as? String) ?: "spotify").lowercase()
                playMedia(query, platform)
            }

            else -> {
                Log.i(TAG, "Comando no manejado o nativo: $command con params: $params")
            }
        }
    }

    private fun setFlashlight(enabled: Boolean) {
        try {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager
            val cameraId = cameraManager?.cameraIdList?.firstOrNull()
            if (cameraManager != null && cameraId != null) {
                cameraManager.setTorchMode(cameraId, enabled)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error controlando linterna: ${e.message}", e)
        }
    }

    private fun setDeviceVolume(percent: Int) {
        try {
            val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
            if (audioManager != null) {
                val maxVol = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
                val targetVol = (percent.coerceIn(0, 100) * maxVol) / 100
                audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, targetVol, AudioManager.FLAG_SHOW_UI)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error ajustando volumen: ${e.message}", e)
        }
    }

    private fun setAlarm(time: String, label: String) {
        try {
            val parts = time.split(":")
            val hour = parts.getOrNull(0)?.toIntOrNull() ?: 8
            val minutes = parts.getOrNull(1)?.toIntOrNull() ?: 0

            val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, hour)
                putExtra(AlarmClock.EXTRA_MINUTES, minutes)
                putExtra(AlarmClock.EXTRA_MESSAGE, label)
                putExtra(AlarmClock.EXTRA_SKIP_UI, false)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error programando alarma: ${e.message}", e)
        }
    }

    private fun setTimer(durationSeconds: Int, label: String) {
        try {
            val intent = Intent(AlarmClock.ACTION_SET_TIMER).apply {
                putExtra(AlarmClock.EXTRA_LENGTH, durationSeconds)
                putExtra(AlarmClock.EXTRA_MESSAGE, label)
                putExtra(AlarmClock.EXTRA_SKIP_UI, false)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error programando temporizador: ${e.message}", e)
        }
    }

    private fun openApplication(appName: String, packageName: String?) {
        try {
            val pm = context.packageManager
            val targetPackage = packageName ?: when (appName.lowercase()) {
                "spotify" -> "com.spotify.music"
                "whatsapp" -> "com.whatsapp"
                "youtube" -> "com.google.android.youtube"
                else -> null
            }

            val launchIntent = if (targetPackage != null) {
                pm.getLaunchIntentForPackage(targetPackage)
            } else {
                null
            }

            if (launchIntent != null) {
                launchIntent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                context.startActivity(launchIntent)
            } else {
                Log.w(TAG, "No se encontró el paquete para: $appName ($packageName)")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error abriendo app: ${e.message}", e)
        }
    }

    private fun makePhoneCall(phoneNumber: String) {
        try {
            val uri = Uri.parse("tel:${phoneNumber.trim()}")
            val intent = Intent(Intent.ACTION_DIAL, uri).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error marcando teléfono: ${e.message}", e)
        }
    }

    private fun sendMessage(recipient: String, message: String, app: String) {
        try {
            val encodedMessage = Uri.encode(message)
            val uri = when (app.lowercase()) {
                "whatsapp" -> {
                    val phoneClean = recipient.replace(Regex("[^0-9]"), "")
                    if (phoneClean.isNotEmpty()) {
                        Uri.parse("https://api.whatsapp.com/send?phone=$phoneClean&text=$encodedMessage")
                    } else {
                        Uri.parse("https://api.whatsapp.com/send?text=$encodedMessage")
                    }
                }
                else -> Uri.parse("sms:${recipient}?body=$encodedMessage")
            }

            val intent = Intent(Intent.ACTION_VIEW, uri).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Error enviando mensaje: ${e.message}", e)
        }
    }

    private fun playMedia(query: String, platform: String) {
        try {
            if (platform.contains("youtube")) {
                val encoded = Uri.encode(query)
                val uri = Uri.parse("https://www.youtube.com/results?search_query=$encoded")
                val intent = Intent(Intent.ACTION_VIEW, uri).apply {
                    setPackage("com.google.android.youtube")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                try {
                    context.startActivity(intent)
                } catch (_: Exception) {
                    val browserIntent = Intent(Intent.ACTION_VIEW, uri).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(browserIntent)
                }
            } else {
                // Spotify
                val playIntent = Intent(android.provider.MediaStore.INTENT_ACTION_MEDIA_PLAY_FROM_SEARCH).apply {
                    setPackage("com.spotify.music")
                    putExtra(android.app.SearchManager.QUERY, query)
                    putExtra(android.provider.MediaStore.EXTRA_MEDIA_FOCUS, "vnd.android.cursor.item/*")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                try {
                    context.startActivity(playIntent)
                } catch (_: Exception) {
                    val searchUri = Uri.parse("spotify:search:${Uri.encode(query)}")
                    val spotifyIntent = Intent(Intent.ACTION_VIEW, searchUri).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(spotifyIntent)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error reproduciendo multimedia ($platform): ${e.message}", e)
        }
    }
}
