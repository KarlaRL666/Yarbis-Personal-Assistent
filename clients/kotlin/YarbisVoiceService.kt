package com.yarbis.client.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.util.Log
import androidx.core.app.NotificationCompat
import com.yarbis.client.audio.WakeWordDetector
import com.yarbis.client.handler.DeviceActionHandler
import com.yarbis.client.network.YarbisApiService
import com.yarbis.client.overlay.YarbisOverlayBubble
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.io.File

/**
 * Servicio en Primer Plano (Foreground Service) de Yarbis.
 *
 * Mantiene a Yarbis escuchando continuamente en segundo plano con bajo consumo,
 * incluso cuando la aplicación no está en pantalla o el usuario interactúa con otras apps.
 *
 * Flujo:
 * 1. El usuario dice "Yarbis..." (o toca la notificación / widget).
 * 2. Aparece instantáneamente la Burbuja Flotante Oculta con animación indicando "Escuchando...".
 * 3. Se captura la orden hasta que el usuario guarda silencio.
 * 4. La burbuja cambia a "Procesando...", envía el audio a [YarbisApiService].
 * 5. Al responder el LLM, [DeviceActionHandler] ejecuta la acción nativa (linterna, app, alarma) y reproduce la voz.
 * 6. La burbuja muestra la respuesta y se oculta de nuevo automáticamente.
 */
class YarbisVoiceService : Service() {

    companion object {
        private const val TAG = "YarbisVoiceService"
        private const val NOTIFICATION_CHANNEL_ID = "yarbis_voice_channel"
        private const val NOTIFICATION_ID = 1001

        const val ACTION_START_LISTENING = "com.yarbis.client.START_LISTENING"
        const val ACTION_STOP_SERVICE = "com.yarbis.client.STOP_SERVICE"
        const val EXTRA_BASE_URL = "extra_base_url"
        const val EXTRA_SESSION_ID = "extra_session_id"

        fun start(context: Context, baseUrl: String = "http://10.0.2.2:8000", sessionId: String = "mobile_kotlin_01") {
            val intent = Intent(context, YarbisVoiceService::class.java).apply {
                action = ACTION_START_LISTENING
                putExtra(EXTRA_BASE_URL, baseUrl)
                putExtra(EXTRA_SESSION_ID, sessionId)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            val intent = Intent(context, YarbisVoiceService::class.java).apply {
                action = ACTION_STOP_SERVICE
            }
            context.stopService(intent)
        }
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private var baseUrl: String = "http://10.0.2.2:8000"
    private var sessionId: String = "mobile_kotlin_01"

    private var overlayBubble: YarbisOverlayBubble? = null
    private var wakeWordDetector: WakeWordDetector? = null
    private var apiService: YarbisApiService? = null
    private var actionHandler: DeviceActionHandler? = null

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "Iniciando YarbisVoiceService...")
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP_SERVICE) {
            stopSelf()
            return START_NOT_STICKY
        }

        baseUrl = intent?.getStringExtra(EXTRA_BASE_URL) ?: baseUrl
        sessionId = intent?.getStringExtra(EXTRA_SESSION_ID) ?: sessionId

        startForegroundWithNotification()
        initializeComponents()

        return START_STICKY
    }

    private fun startForegroundWithNotification() {
        val stopIntent = Intent(this, YarbisVoiceService::class.java).apply {
            action = ACTION_STOP_SERVICE
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            0,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification: Notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("Yarbis Asistente de Voz Activo")
            .setContentText("Diga 'Yarbis' en cualquier momento para solicitar una acción.")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Detener", stopPendingIntent)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun initializeComponents() {
        apiService = YarbisApiService(baseUrl = baseUrl)
        actionHandler = DeviceActionHandler(context = this, baseUrl = baseUrl)

        // Verificar si la aplicación tiene permiso de Overlay (SYSTEM_ALERT_WINDOW)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
            Log.w(TAG, "Permiso SYSTEM_ALERT_WINDOW no concedido. La burbuja no podrá mostrarse.")
        }

        // Crear la burbuja flotante oculta
        if (overlayBubble == null) {
            overlayBubble = YarbisOverlayBubble(
                context = this,
                onBubbleClick = {
                    // Si el usuario toca la burbuja mientras escucha o procesa, puede cancelar o re-escuchar
                    overlayBubble?.hideBubble()
                }
            )
        }

        // Iniciar detector de Wake Word en segundo plano
        if (wakeWordDetector == null) {
            wakeWordDetector = WakeWordDetector(
                context = this,
                onWakeWordTriggered = {
                    Log.i(TAG, "Wake word 'Yarbis' detectado! Mostrando burbuja oculta.")
                    overlayBubble?.showListening("Yarbis escuchando solicitud...")
                },
                onCommandRecorded = { audioFile ->
                    handleRecordedAudio(audioFile)
                },
                onError = { errorMsg ->
                    Log.e(TAG, "Error en detector: $errorMsg")
                }
            )
            wakeWordDetector?.startListening()
        }
    }

    private fun handleRecordedAudio(audioFile: File) {
        overlayBubble?.showProcessing("Procesando orden...")

        serviceScope.launch(Dispatchers.IO) {
            try {
                val api = apiService ?: YarbisApiService(baseUrl = baseUrl)
                // Enviamos el audio grabado al endpoint /api/v1/voice/process
                val result = api.processVoiceAudio(
                    audioFile = audioFile,
                    sessionId = sessionId,
                    requireWakeWord = false, // Ya fue validado o activado por voz
                    generateAudio = true,
                    includeAudioBase64 = true
                )

                result.onSuccess { response ->
                    Log.i(TAG, "Respuesta recibida: ${response.textResponse}")

                    serviceScope.launch(Dispatchers.Main) {
                        // 1. Mostrar la respuesta en la burbuja
                        overlayBubble?.showSpeaking(response.textResponse)

                        // 2. Ejecutar la acción de hardware y reproducir audio TTS
                        actionHandler?.handleResponse(response) {
                            // Cuando termina de hablar, ocultar la burbuja suavemente tras 1.5s
                            overlayBubble?.hideBubble(delayMillis = 1500)
                        }
                    }
                }.onFailure { ex ->
                    Log.e(TAG, "Error de red al procesar voz: ${ex.message}", ex)
                    serviceScope.launch(Dispatchers.Main) {
                        overlayBubble?.showProcessing("Error al conectar con Yarbis")
                        overlayBubble?.hideBubble(delayMillis = 2000)
                    }
                }
            } finally {
                // Eliminar archivo de audio temporal grabado
                if (audioFile.exists()) {
                    audioFile.delete()
                }
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "Servicio de Escucha Yarbis",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Mantiene activo el asistente de voz en segundo plano"
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.i(TAG, "Destruyendo YarbisVoiceService...")
        serviceScope.cancel()
        wakeWordDetector?.stopListening()
        wakeWordDetector = null
        overlayBubble?.destroy()
        overlayBubble = null
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
