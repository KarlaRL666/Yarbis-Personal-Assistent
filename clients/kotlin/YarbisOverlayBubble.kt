package com.yarbis.client.overlay

import android.animation.ObjectAnimator
import android.animation.PropertyValuesHolder
import android.animation.ValueAnimator
import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.view.animation.AccelerateDecelerateInterpolator
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Estados visuales de la Burbuja Flotante de Yarbis.
 */
enum class BubbleState {
    HIDDEN,        // Oculta completamente en reposo
    LISTENING,     // Mostrada: capturando voz del usuario (brillo cian pulsante)
    PROCESSING,    // Procesando solicitud con Yarbis API / LLM (brillo violeta giratorio)
    SPEAKING,      // Hablando: reproduciendo respuesta de voz (brillo verde esmeralda)
    ERROR          // Indicador de error temporal
}

/**
 * Burbuja Flotante Oculta (Overlay Bubble) para Yarbis en Android.
 *
 * Se mantiene completamente invisible en segundo plano hasta que se detecta la palabra clave "Yarbis".
 * Al activarse, aparece en pantalla con animación suave sobre cualquier aplicación abierta,
 * proporcionando retroalimentación visual clara de que Yarbis está escuchando la solicitud.
 */
class YarbisOverlayBubble(
    private val context: Context,
    private val onBubbleClick: (() -> Unit)? = null
) {
    private val windowManager: WindowManager =
        context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val mainHandler = Handler(Looper.getMainLooper())

    private var rootView: FrameLayout? = null
    private var bubbleContainer: LinearLayout? = null
    private var iconView: TextView? = null
    private var statusTextView: TextView? = null
    private var pulseAnimator: ObjectAnimator? = null

    private var windowParams: WindowManager.LayoutParams? = null
    private var currentState: BubbleState = BubbleState.HIDDEN
    private var isAttached = false

    // Coordenadas para arrastrar la burbuja (Drag & Drop)
    private var initialX = 0
    private var initialY = 0
    private var initialTouchX = 0f
    private var initialTouchY = 0f
    private var isDragging = false

    init {
        mainHandler.post {
            createBubbleViews()
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun createBubbleViews() {
        val layoutType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        windowParams = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                    WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = dpToPx(60) // Ubicada en la parte superior central de la pantalla
        }

        // Contenedor Raíz
        rootView = FrameLayout(context).apply {
            visibility = View.GONE
            alpha = 0f
        }

        // Tarjeta / Burbuja Flotante con estilo Glassmorphism futurista
        bubbleContainer = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dpToPx(16), dpToPx(10), dpToPx(20), dpToPx(10))

            // Fondo translúcido oscuro con bordes redondeados y borde neón
            background = createPillBackground(Color.parseColor("#E60D1117"), Color.parseColor("#00E5FF"))
            elevation = dpToPx(12).toFloat()
        }

        // Icono / Indicador visual (Micrófono o estado)
        iconView = TextView(context).apply {
            text = "🎙️"
            textSize = 22f
            setPadding(0, 0, dpToPx(10), 0)
        }

        // Texto informativo del estado actual
        statusTextView = TextView(context).apply {
            text = "Yarbis te escucha..."
            setTextColor(Color.WHITE)
            textSize = 14f
            typeface = android.graphics.Typeface.DEFAULT_BOLD
            maxWidth = dpToPx(240)
        }

        bubbleContainer?.addView(iconView)
        bubbleContainer?.addView(statusTextView)
        rootView?.addView(bubbleContainer)

        // Configurar arrastre táctil (Drag & Drop) y clic
        bubbleContainer?.setOnTouchListener { _, event ->
            handleTouch(event)
        }

        // Preparar animación de pulsación de brillo
        bubbleContainer?.let { container ->
            pulseAnimator = ObjectAnimator.ofPropertyValuesHolder(
                container,
                PropertyValuesHolder.ofFloat(View.SCALE_X, 1.0f, 1.06f, 1.0f),
                PropertyValuesHolder.ofFloat(View.SCALE_Y, 1.0f, 1.06f, 1.0f)
            ).apply {
                duration = 1200
                repeatCount = ValueAnimator.INFINITE
                repeatMode = ValueAnimator.RESTART
                interpolator = AccelerateDecelerateInterpolator()
            }
        }

        try {
            windowManager.addView(rootView, windowParams)
            isAttached = true
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun handleTouch(event: MotionEvent): Boolean {
        val params = windowParams ?: return false
        val view = rootView ?: return false

        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                initialX = params.x
                initialY = params.y
                initialTouchX = event.rawX
                initialTouchY = event.rawY
                isDragging = false
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = (event.rawX - initialTouchX).toInt()
                val dy = (event.rawY - initialTouchY).toInt()
                if (Math.abs(dx) > 10 || Math.abs(dy) > 10) {
                    isDragging = true
                }
                if (isDragging) {
                    params.x = initialX + dx
                    params.y = initialY + dy
                    try {
                        windowManager.updateViewLayout(view, params)
                    } catch (_: Exception) {}
                }
                return true
            }
            MotionEvent.ACTION_UP -> {
                if (!isDragging) {
                    onBubbleClick?.invoke()
                }
                return true
            }
        }
        return false
    }

    /**
     * Hace aparecer la burbuja en modo de escucha cuando se detecta "Yarbis".
     */
    fun showListening(message: String = "Yarbis escuchando solicitud...") {
        mainHandler.post {
            updateState(BubbleState.LISTENING, "🎙️", message, Color.parseColor("#00E5FF"))
            showWithAnimation()
            pulseAnimator?.start()
        }
    }

    /**
     * Cambia la burbuja a estado de procesamiento mientras el LLM / STT trabaja.
     */
    fun showProcessing(message: String = "Procesando orden...") {
        mainHandler.post {
            updateState(BubbleState.PROCESSING, "⚡", message, Color.parseColor("#BD00FF"))
        }
    }

    /**
     * Muestra la burbuja mientras Yarbis responde o ejecuta la acción.
     */
    fun showSpeaking(responsePreview: String) {
        mainHandler.post {
            val preview = if (responsePreview.length > 40) {
                responsePreview.take(37) + "..."
            } else {
                responsePreview
            }
            updateState(BubbleState.SPEAKING, "🤖", preview, Color.parseColor("#00FF88"))
        }
    }

    /**
     * Oculta suavemente la burbuja flotante y detiene las animaciones.
     *
     * @param delayMillis Tiempo de espera opcional antes de ocultarse (para permitir leer la respuesta).
     */
    fun hideBubble(delayMillis: Long = 0) {
        mainHandler.postDelayed({
            pulseAnimator?.cancel()
            rootView?.animate()
                ?.alpha(0f)
                ?.scaleX(0.7f)
                ?.scaleY(0.7f)
                ?.setDuration(300)
                ?.withEndAction {
                    rootView?.visibility = View.GONE
                    currentState = BubbleState.HIDDEN
                }
                ?.start()
        }, delayMillis)
    }

    private fun showWithAnimation() {
        val root = rootView ?: return
        root.scaleX = 0.7f
        root.scaleY = 0.7f
        root.alpha = 0f
        root.visibility = View.VISIBLE

        root.animate()
            .alpha(1f)
            .scaleX(1f)
            .scaleY(1f)
            .setDuration(280)
            .setInterpolator(AccelerateDecelerateInterpolator())
            .start()
    }

    private fun updateState(state: BubbleState, icon: String, text: String, borderColor: Int) {
        currentState = state
        iconView?.text = icon
        statusTextView?.text = text
        bubbleContainer?.background = createPillBackground(Color.parseColor("#E60D1117"), borderColor)
    }

    private fun createPillBackground(bgColor: Int, strokeColor: Int): GradientDrawable {
        return GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = dpToPx(30).toFloat()
            setColor(bgColor)
            setStroke(dpToPx(2), strokeColor)
        }
    }

    private fun dpToPx(dp: Int): Int {
        return TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP,
            dp.toFloat(),
            context.resources.displayMetrics
        ).toInt()
    }

    /**
     * Libera los recursos del WindowManager al destruir el servicio.
     */
    fun destroy() {
        mainHandler.post {
            pulseAnimator?.cancel()
            if (isAttached && rootView != null) {
                try {
                    windowManager.removeView(rootView)
                } catch (_: Exception) {}
                isAttached = false
            }
        }
    }
}
