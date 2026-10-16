package com.yarbis.client.network

import com.google.gson.Gson
import com.yarbis.client.model.YarbisResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Cliente HTTP en Kotlin para el backend de Yarbis.
 * Maneja peticiones asíncronas seguras con Coroutines y OkHttp.
 */
class YarbisApiService(
    // 10.0.2.2 es localhost en el emulador de Android Studio. En dispositivo físico, usa la IP local (ej. 192.168.1.50).
    val baseUrl: String = "http://10.0.2.2:8000"
) {
    private val gson = Gson()
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    /**
     * Envía un archivo de audio grabado con MediaRecorder / AudioRecord (.m4a, .wav, .3gp, etc.)
     * Endpoint: POST /api/v1/voice/process
     */
    suspend fun processVoiceAudio(
        audioFile: File,
        sessionId: String = "mobile_kotlin_01",
        requireWakeWord: Boolean = false,
        generateAudio: Boolean = true,
        includeAudioBase64: Boolean = true
    ): Result<YarbisResponse> = withContext(Dispatchers.IO) {
        try {
            val mimeType = when (audioFile.extension.lowercase()) {
                "wav" -> "audio/wav"
                "3gp" -> "video/3gpp"
                "aac" -> "audio/aac"
                "mp3" -> "audio/mpeg"
                else -> "audio/m4a"
            }

            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "file",
                    audioFile.name,
                    audioFile.asRequestBody(mimeType.toMediaType())
                )
                .addFormDataPart("session_id", sessionId)
                .addFormDataPart("require_wake_word", requireWakeWord.toString())
                .addFormDataPart("generate_audio", generateAudio.toString())
                .addFormDataPart("include_audio_base64", includeAudioBase64.toString())
                .build()

            val request = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/v1/voice/process")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    val errorBody = response.body?.string() ?: ""
                    return@withContext Result.failure(
                        IOException("Error HTTP ${response.code}: $errorBody")
                    )
                }

                val bodyString = response.body?.string()
                    ?: return@withContext Result.failure(IOException("Cuerpo de respuesta vacío"))

                val yarbisResponse = gson.fromJson(bodyString, YarbisResponse::class.java)
                Result.success(yarbisResponse)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Envía un comando en texto directo (modo teclado o pruebas).
     * Endpoint: POST /api/v1/command/process
     */
    suspend fun processTextCommand(
        text: String,
        sessionId: String = "mobile_kotlin_01",
        requireWakeWord: Boolean = false,
        generateAudio: Boolean = true,
        includeAudioBase64: Boolean = false
    ): Result<YarbisResponse> = withContext(Dispatchers.IO) {
        try {
            val jsonPayload = gson.toJson(
                mapOf(
                    "text" to text,
                    "session_id" to sessionId,
                    "require_wake_word" to requireWakeWord,
                    "generate_audio" to generateAudio,
                    "include_audio_base64" to includeAudioBase64
                )
            )

            val requestBody = jsonPayload.toRequestBody("application/json; charset=utf-8".toMediaType())

            val request = Request.Builder()
                .url("${baseUrl.trimEnd('/')}/api/v1/command/process")
                .post(requestBody)
                .build()

            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    val errorBody = response.body?.string() ?: ""
                    return@withContext Result.failure(
                        IOException("Error HTTP ${response.code}: $errorBody")
                    )
                }

                val bodyString = response.body?.string()
                    ?: return@withContext Result.failure(IOException("Cuerpo de respuesta vacío"))

                val yarbisResponse = gson.fromJson(bodyString, YarbisResponse::class.java)
                Result.success(yarbisResponse)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
