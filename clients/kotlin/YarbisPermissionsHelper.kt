package com.yarbis.client.util

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * Utilidad para solicitar y verificar permisos necesarios para Yarbis:
 * 1. Superposición en pantalla (SYSTEM_ALERT_WINDOW) para la burbuja flotante.
 * 2. Micrófono (RECORD_AUDIO) para la escucha en segundo plano.
 * 3. Notificaciones (POST_NOTIFICATIONS) para Android 13+.
 */
object YarbisPermissionsHelper {

    const val REQUEST_CODE_AUDIO_PERMS = 2001
    const val REQUEST_CODE_OVERLAY_PERM = 2002

    fun hasRecordAudioPermission(context: Context): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun hasOverlayPermission(context: Context): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Settings.canDrawOverlays(context)
        } else {
            true
        }
    }

    fun requestRecordAudioPermission(activity: Activity) {
        val permissions = mutableListOf(android.Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(android.Manifest.permission.POST_NOTIFICATIONS)
        }
        ActivityCompat.requestPermissions(
            activity,
            permissions.toTypedArray(),
            REQUEST_CODE_AUDIO_PERMS
        )
    }

    fun requestOverlayPermission(activity: Activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(activity)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${activity.packageName}")
            )
            activity.startActivityForResult(intent, REQUEST_CODE_OVERLAY_PERM)
        }
    }

    fun isAllPermissionsGranted(context: Context): Boolean {
        return hasRecordAudioPermission(context) && hasOverlayPermission(context)
    }
}
