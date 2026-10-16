"""
Cliente de Escritorio (Desktop) con Burbuja Flotante Oculta para Yarbis.
========================================================================

Características:
1. Escucha en segundo plano: Funciona mientras usas cualquier programa (navegador, juegos, editor de código).
2. Detección de Wake Word: Al decir "Yarbis" (o variantes: "Jarvis", "Oye Yarbis"), se despierta automáticamente.
3. Burbuja Flotante Oculta (HUD):
   - En reposo permanece 100% invisible.
   - Al escuchar "Yarbis", aparece de inmediato en la pantalla como una burbuja flotante futurista de estilo Glassmorphism.
   - Muestra retroalimentación visual en tiempo real ("🎙️ Escuchando...", "⚡ Procesando...", "💬 Respuesta").
   - Reproduce el audio de voz de Yarbis.
   - Se oculta automáticamente al terminar la interacción.
"""

import io
import os
import sys
import time
import tempfile
import threading
import tkinter as tk
from tkinter import font as tkfont
import urllib.request
import json
import base64

# Agregar raíz del proyecto al path para reutilizar validador de wake word
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.core.wake_word import WakeWordValidator

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False


class YarbisFloatingBubble:
    """Ventana flotante de burbuja oculta con diseño moderno e indicador visual."""

    def __init__(self, on_cancel_callback=None):
        self.root = tk.Tk()
        self.root.title("Yarbis Floating Bubble")
        self.root.overrideredirect(True)  # Sin bordes estándar de ventana
        self.root.attributes("-topmost", True)  # Siempre visible por encima
        self.root.config(bg="#0D1117")

        # Color clave para transparencia en Windows si se desea
        try:
            self.root.attributes("-alpha", 0.95)
        except Exception:
            pass

        # Dimensiones y posicionamiento en parte superior central
        self.width = 440
        self.height = 70
        screen_w = self.root.winfo_screenwidth()
        pos_x = (screen_w - self.width) // 2
        pos_y = 50
        self.root.geometry(f"{self.width}x{self.height}+{pos_x}+{pos_y}")

        # Contenedor con borde neón
        self.frame = tk.Frame(
            self.root,
            bg="#0D1117",
            highlightbackground="#00E5FF",
            highlightcolor="#00E5FF",
            highlightthickness=2,
            padx=14,
            pady=10
        )
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Icono / Emoji de estado
        self.icon_label = tk.Label(
            self.frame,
            text="🎙️",
            font=("Segoe UI Emoji", 20),
            bg="#0D1117",
            fg="#00E5FF"
        )
        self.icon_label.pack(side=tk.LEFT, padx=(0, 10))

        # Texto de estado
        self.status_label = tk.Label(
            self.frame,
            text="Yarbis escuchando...",
            font=("Segoe UI", 11, "bold"),
            bg="#0D1117",
            fg="#FFFFFF",
            anchor="w",
            wraplength=340,
            justify=tk.LEFT
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Arrastre con ratón (Drag & Drop)
        self.frame.bind("<Button-1>", self._start_drag)
        self.frame.bind("<B1-Motion>", self._do_drag)
        self.status_label.bind("<Button-1>", self._start_drag)
        self.status_label.bind("<B1-Motion>", self._do_drag)
        self.icon_label.bind("<Button-1>", self._start_drag)
        self.icon_label.bind("<B1-Motion>", self._do_drag)

        self._drag_x = 0
        self._drag_y = 0

        # Iniciar inicialmente OCULTA
        self.root.withdraw()
        self.is_visible = False
        self._hide_timer = None

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def show_listening(self, text="Yarbis te escucha... ¿Qué necesitas?"):
        """Muestra la burbuja flotante en estado de escucha activa."""
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None

        def _update():
            self.frame.config(highlightbackground="#00E5FF")
            self.icon_label.config(text="🎙️", fg="#00E5FF")
            self.status_label.config(text=text, fg="#00E5FF")
            self.root.deiconify()
            self.root.lift()
            self.is_visible = True

        self.root.after(0, _update)

    def show_processing(self, text="Procesando solicitud..."):
        """Actualiza la burbuja a estado de procesamiento."""
        def _update():
            self.frame.config(highlightbackground="#BD00FF")
            self.icon_label.config(text="⚡", fg="#BD00FF")
            self.status_label.config(text=text, fg="#BD00FF")

        self.root.after(0, _update)

    def show_speaking(self, text):
        """Muestra la respuesta de Yarbis."""
        def _update():
            short_text = text if len(text) <= 90 else text[:87] + "..."
            self.frame.config(highlightbackground="#00FF88")
            self.icon_label.config(text="🤖", fg="#00FF88")
            self.status_label.config(text=short_text, fg="#FFFFFF")

        self.root.after(0, _update)

    def hide_bubble(self, delay_ms=0):
        """Oculta suavemente la burbuja flotante."""
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)

        def _do_hide():
            self.root.withdraw()
            self.is_visible = False
            self._hide_timer = None

        if delay_ms <= 0:
            self.root.after(0, _do_hide)
        else:
            self._hide_timer = self.root.after(delay_ms, _do_hide)


class YarbisBackgroundAssistant:
    """Asistente de fondo que monitorea el micrófono y coordina la burbuja y la API."""

    def __init__(self, api_url="http://127.0.0.1:8000"):
        self.api_url = api_url.rstrip("/")
        self.bubble = YarbisFloatingBubble()
        self.recognizer = sr.Recognizer() if SPEECH_AVAILABLE else None
        self.session_id = "desktop_session_01"
        self.is_running = True

    def start(self):
        """Inicia el hilo de escucha en segundo plano y el loop de la interfaz gráfica."""
        if not SPEECH_AVAILABLE:
            print("[AVISO] SpeechRecognition o PyAudio no están disponibles en el entorno.")
            print("[AVISO] La burbuja interactiva puede probarse en modo manual.")

        # Iniciar hilo de escucha en background
        worker = threading.Thread(target=self._background_listening_loop, daemon=True)
        worker.start()

        print("=" * 60)
        print("🚀 Yarbis Desktop con Burbuja Oculta iniciado.")
        print(f"📡 Conectado a Backend: {self.api_url}")
        print("👂 Escuchando en segundo plano...")
        print("💡 Di 'Yarbis' en voz alta en cualquier momento.")
        print("=" * 60)

        # Loop principal de la ventana de Tkinter
        try:
            self.bubble.root.mainloop()
        except KeyboardInterrupt:
            self.is_running = False

    def _background_listening_loop(self):
        """Monitorea continuamente el micrófono para detectar el Wake Word 'Yarbis'."""
        if not SPEECH_AVAILABLE:
            return

        with sr.Microphone() as source:
            print("[Info] Calibrando sensibilidad ambiental del micrófono...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            self.recognizer.energy_threshold = max(self.recognizer.energy_threshold, 300)
            self.recognizer.dynamic_energy_threshold = True
            print("[Info] Micrófono listo. Yarbis en espera oculta.")

            while self.is_running:
                try:
                    # Capturar segmento de audio pasivo
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=4)
                    try:
                        # Reconocimiento rápido en español
                        text = self.recognizer.recognize_google(audio, language="es-ES")
                        if not text:
                            continue

                        # Validar si contiene la palabra clave 'Yarbis'
                        is_wake, cleaned = WakeWordValidator.detect_and_clean(text)
                        if is_wake:
                            print(f"\n[🔔 WAKE WORD DETECTADO]: '{text}'")
                            self._handle_wake_activation(source, cleaned)
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        time.sleep(1)
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    time.sleep(0.5)

    def _handle_wake_activation(self, source, immediate_command: str):
        """Activa la burbuja flotante y procesa la solicitud."""
        # 1. Mostrar la burbuja flotante de inmediato sobre cualquier app
        self.bubble.show_listening("🎙️ Yarbis escuchando... Te oigo.")

        command_text = immediate_command.strip()

        # Si el usuario solo dijo "Yarbis", capturar la orden siguiente:
        if not command_text:
            try:
                # Escuchar la solicitud completa del usuario
                followup_audio = self.recognizer.listen(source, timeout=4, phrase_time_limit=8)
                self.bubble.show_processing("⚡ Transcribiendo tu solicitud...")
                command_text = self.recognizer.recognize_google(followup_audio, language="es-ES")
            except Exception:
                command_text = ""

        if not command_text:
            self.bubble.show_speaking("No alcancé a escucharte bien.")
            self.bubble.hide_bubble(delay_ms=2500)
            return

        print(f"[Orden del usuario]: '{command_text}'")
        self.bubble.show_processing(f"⚡ Procesando: \"{command_text}\"")

        # 2. Enviar a la API de Yarbis
        response_data = self._send_command_to_api(command_text)

        if response_data:
            text_response = response_data.get("text_response", "Comando procesado.")
            audio_b64 = response_data.get("audio_base64")

            print(f"[Yarbis responde]: {text_response}")
            self.bubble.show_speaking(text_response)

            # Reproducir audio sintetizado si está disponible
            if audio_b64:
                self._play_audio_base64(audio_b64)

            # Ocultar automáticamente la burbuja tras terminar
            self.bubble.hide_bubble(delay_ms=3000)
        else:
            self.bubble.show_speaking("Error al conectar con el servidor Yarbis.")
            self.bubble.hide_bubble(delay_ms=2500)

    def _send_command_to_api(self, text: str):
        """Envía el comando por HTTP POST a /api/v1/command/process."""
        endpoint = f"{self.api_url}/api/v1/command/process"
        payload = json.dumps({
            "text": text,
            "session_id": self.session_id,
            "require_wake_word": False,
            "generate_audio": True,
            "include_audio_base64": True
        }).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Error de conexión con Backend]: {e}")
            return None

    def _play_audio_base64(self, b64_string: str):
        """Guarda y reproduce el audio en segundo plano sin congelar la interfaz."""
        def _play():
            try:
                audio_bytes = base64.b64decode(b64_string)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    tf.write(audio_bytes)
                    temp_name = tf.name

                # En Windows reproducir mediante PowerShell o comando nativo silencioso
                if sys.platform == "win32":
                    import subprocess
                    ps_cmd = f"(New-Object Media.SoundPlayer '{temp_name}').PlaySync()" if temp_name.endswith(".wav") else f"Add-Type -AssemblyName presentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{temp_name}'); $p.Play(); Start-Sleep -Seconds 3"
                    subprocess.run(["powershell", "-c", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    os.remove(temp_name)
                except Exception:
                    pass
            except Exception as e:
                print(f"[Error reproduciendo audio]: {e}")

        threading.Thread(target=_play, daemon=True).start()


if __name__ == "__main__":
    assistant = YarbisBackgroundAssistant()
    assistant.start()
