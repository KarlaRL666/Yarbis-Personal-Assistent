package com.yarbis.client.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Detector de Wake Word ("Yarbis") y Grabador de Solicitud en Segundo Plano para Android.
 *
 * Monitorea el micrófono de forma eficiente y continua. Al detectar voz o la invocación "Yarbis",
 * activa el callback [onWakeWordTriggered], captura la solicitud del usuario hasta detectar silencio
 * y entrega el archivo de audio para su envío al servidor Yarbis.
 */
class WakeWordDetector(
    private val context: Context,
    private val onWakeWordTriggered: () -> Unit,
    private val onCommandRecorded: (File) -> Unit,
    private val onError: (String) -> Unit = {}
) {
    companion object {
        private const val TAG = "WakeWordDetector"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val SILENCE_THRESHOLD_RMS = 450.0 // Umbral RMS para detectar fin de orden
        private const val SILENCE_DURATION_MS = 1500L  // 1.5s de silencio marca el final del comando
    }

    private val isRunning = AtomicBoolean(false)
    private val isCapturingCommand = AtomicBoolean(false)
    private var audioRecord: AudioRecord? = null
    private var workerThread: Thread? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    private var activeOutputFile: File? = null
    private var outputStream: FileOutputStream? = null
    private var totalPcmBytes = 0

    @SuppressLint("MissingPermission")
    fun startListening() {
        if (isRunning.get()) return

        val minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
        val bufferSize = Math.max(minBufferSize, 4096)

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                SAMPLE_RATE,
                CHANNEL_CONFIG,
                AUDIO_FORMAT,
                bufferSize
            )

            if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
                onError("No se pudo inicializar AudioRecord. Verifique permisos de micrófono.")
                return
            }

            audioRecord?.startRecording()
            isRunning.set(true)

            workerThread = Thread({
                processAudioStream(bufferSize)
            }, "YarbisWakeWordThread").apply {
                priority = Thread.NORM_PRIORITY + 2
                start()
            }
            Log.i(TAG, "Escucha en segundo plano iniciada correctamente.")
        } catch (e: Exception) {
            Log.e(TAG, "Error iniciando escucha: ${e.message}", e)
            onError("Fallo al iniciar micrófono: ${e.message}")
        }
    }

    /**
     * Ciclo continuo de procesamiento de audio en segundo plano.
     */
    private fun processAudioStream(bufferSize: Int) {
        val audioBuffer = ShortArray(bufferSize / 2)
        var consecutiveSilenceMs = 0L
        val loopIntervalMs = (audioBuffer.size * 1000L) / SAMPLE_RATE

        while (isRunning.get()) {
            val readSamples = audioRecord?.read(audioBuffer, 0, audioBuffer.size) ?: -1
            if (readSamples <= 0) continue

            // Calcular nivel de energía acústica RMS
            var sum = 0.0
            for (i in 0 until readSamples) {
                sum += (audioBuffer[i] * audioBuffer[i]).toDouble()
            }
            val rms = Math.sqrt(sum / readSamples)

            // Si está en modo captura de orden:
            if (isCapturingCommand.get()) {
                // Escribir bytes PCM en archivo temporal
                writeShortsToPcm(audioBuffer, readSamples)

                if (rms < SILENCE_THRESHOLD_RMS) {
                    consecutiveSilenceMs += loopIntervalMs
                    if (consecutiveSilenceMs >= SILENCE_DURATION_MS) {
                        // El usuario terminó de hablar
                        finishCommandCapture()
                        consecutiveSilenceMs = 0L
                    }
                } else {
                    consecutiveSilenceMs = 0L
                }
            } else {
                // Modo reposo: Detección de palabra clave o activación
                // Cuando se detecta voz sobre el umbral tras reposo:
                if (rms > (SILENCE_THRESHOLD_RMS * 1.5)) {
                    triggerListeningState()
                    // Comenzar a escribir de inmediato para incluir la orden
                    writeShortsToPcm(audioBuffer, readSamples)
                }
            }
        }
    }

    /**
     * Activa el estado de escucha de Yarbis y muestra la burbuja flotante.
     */
    fun triggerListeningState() {
        if (isCapturingCommand.get()) return

        isCapturingCommand.set(true)
        totalPcmBytes = 0

        try {
            val cacheDir = context.cacheDir
            activeOutputFile = File.createTempFile("yarbis_voice_request_", ".wav", cacheDir)
            outputStream = FileOutputStream(activeOutputFile)
            // Escribir encabezado WAV provisional de 44 bytes
            outputStream?.write(ByteArray(44))
        } catch (e: Exception) {
            Log.e(TAG, "Error preparando archivo de captura: ${e.message}")
        }

        mainHandler.post {
            onWakeWordTriggered()
        }
    }

    private fun writeShortsToPcm(shorts: ShortArray, length: Int) {
        try {
            val fos = outputStream ?: return
            val bytes = ByteArray(length * 2)
            for (i in 0 until length) {
                val s = shorts[i].toInt()
                bytes[i * 2] = (s and 0x00FF).toByte()
                bytes[i * 2 + 1] = ((s shr 8) and 0x00FF).toByte()
            }
            fos.write(bytes)
            totalPcmBytes += bytes.size
        } catch (e: Exception) {
            Log.e(TAG, "Error escribiendo audio PCM: ${e.message}")
        }
    }

    private fun finishCommandCapture() {
        isCapturingCommand.set(false)
        try {
            outputStream?.flush()
            outputStream?.close()
            outputStream = null

            val file = activeOutputFile
            if (file != null && file.exists() && totalPcmBytes > 3200) { // Al menos 0.1s de audio
                // Actualizar encabezados WAV canónicos con el tamaño final exacto
                writeWavHeader(file, totalPcmBytes, SAMPLE_RATE, 1, 16)
                mainHandler.post {
                    onCommandRecorded(file)
                }
            } else {
                file?.delete()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error finalizando captura de audio: ${e.message}")
        }
    }

    /**
     * Actualiza el encabezado WAV RIFF canónico para compatibilidad total con Whisper / Yarbis Backend.
     */
    private fun writeWavHeader(
        wavFile: File,
        pcmDataSize: Int,
        sampleRate: Int,
        channels: Int,
        bitsPerSample: Int
    ) {
        val totalFileSize = pcmDataSize + 36
        val byteRate = sampleRate * channels * (bitsPerSample / 8)

        RandomAccessFile(wavFile, "rw").use { raf ->
            raf.seek(0)
            raf.writeBytes("RIFF")
            raf.write(intToByteArray(totalFileSize))
            raf.writeBytes("WAVE")
            raf.writeBytes("fmt ")
            raf.write(intToByteArray(16)) // Subchunk1Size (16 para PCM)
            raf.write(shortToByteArray(1))  // AudioFormat (1 para PCM)
            raf.write(shortToByteArray(channels.toShort()))
            raf.write(intToByteArray(sampleRate))
            raf.write(intToByteArray(byteRate))
            raf.write(shortToByteArray(((channels * bitsPerSample) / 8).toShort())) // BlockAlign
            raf.write(shortToByteArray(bitsPerSample.toShort()))
            raf.writeBytes("data")
            raf.write(intToByteArray(pcmDataSize))
        }
    }

    private fun intToByteArray(value: Int): ByteArray = byteArrayOf(
        (value and 0xFF).toByte(),
        ((value shr 8) and 0xFF).toByte(),
        ((value shr 16) and 0xFF).toByte(),
        ((value shr 24) and 0xFF).toByte()
    )

    private fun shortToByteArray(value: Short): ByteArray = byteArrayOf(
        (value.toInt() and 0xFF).toByte(),
        ((value.toInt() shr 8) and 0xFF).toByte()
    )

    fun stopListening() {
        isRunning.set(false)
        isCapturingCommand.set(false)

        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null

        try {
            workerThread?.interrupt()
        } catch (_: Exception) {}
        workerThread = null

        try {
            outputStream?.close()
        } catch (_: Exception) {}
        outputStream = null
    }
}
