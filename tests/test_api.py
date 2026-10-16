import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["assistant"] == "Yarbis"


@pytest.mark.asyncio
async def test_command_process_device_control():
    payload = {
        "text": "Yarbis, enciende la linterna",
        "session_id": "test_session_1",
        "require_wake_word": False,
        "generate_audio": False
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/command/process", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["action_type"] == "device_control"
        assert data["command"] == "toggle_flashlight"
        assert data["parameters"]["state"] is True
        assert "linterna" in data["text_response"].lower()


@pytest.mark.asyncio
async def test_command_process_conversational_query():
    payload = {
        "text": "¿Cuál es la distancia a la luna?",
        "session_id": "test_session_2",
        "require_wake_word": False,
        "generate_audio": False
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/command/process", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["action_type"] == "conversational_query"
        assert data["command"] is None
        assert "distancia a la luna" in data["text_response"] or len(data["text_response"]) > 0


@pytest.mark.asyncio
async def test_command_wake_word_required_rejected():
    payload = {
        "text": "enciende la linterna",
        "session_id": "test_session_3",
        "require_wake_word": True,
        "generate_audio": False
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/command/process", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["action_type"] == "conversational_query"
        assert "yarbis" in data["text_response"].lower()


@pytest.mark.asyncio
async def test_voice_process_multipart():
    dummy_wav_bytes = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    files = {
        "file": ("test_audio.wav", dummy_wav_bytes, "audio/wav")
    }
    data = {
        "session_id": "session_voice_test",
        "require_wake_word": "false",
        "generate_audio": "false"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/voice/process", files=files, data=data)
        assert response.status_code == 200
        res = response.json()
        assert "action_type" in res
        assert "command" in res
        assert "parameters" in res
        assert "text_response" in res


@pytest.mark.asyncio
async def test_voice_process_m4a_format():
    # Kotlin/Android comúnmente envía audio en contenedor .m4a (AAC)
    dummy_m4a_bytes = b"\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00M4A mp42isom\x00\x00\x00\x00"
    files = {
        "file": ("kotlin_recording.m4a", dummy_m4a_bytes, "audio/m4a")
    }
    data = {
        "session_id": "session_m4a_test",
        "require_wake_word": "false",
        "generate_audio": "false"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/voice/process", files=files, data=data)
        assert response.status_code == 200
        res = response.json()
        assert res["action_type"] in ["device_control", "conversational_query"]


@pytest.mark.asyncio
async def test_voice_process_android_3gp_format():
    # Android MediaRecorder también puede generar .3gp (AMR/AAC)
    dummy_3gp_bytes = b"\x00\x00\x00\x14ftyp3gp4\x00\x00\x00\x003gp4"
    files = {
        "file": ("kotlin_recording.3gp", dummy_3gp_bytes, "video/3gpp")
    }
    data = {
        "session_id": "session_3gp_test",
        "require_wake_word": "false",
        "generate_audio": "false"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/voice/process", files=files, data=data)
        assert response.status_code == 200
        res = response.json()
        assert res["action_type"] in ["device_control", "conversational_query"]


@pytest.mark.asyncio
async def test_voice_process_invalid_extension():
    # Archivos no de audio deben ser rechazados con 400 Bad Request
    files = {
        "file": ("malicious_or_wrong.txt", b"este no es un audio", "text/plain")
    }
    data = {
        "session_id": "session_bad_ext"
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/voice/process", files=files, data=data)
        assert response.status_code == 400
        assert "no soportado" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_command_process_with_base64_and_relative_url():
    # Verifica que la URL de audio sea relativa (/api/v1/voice/audio/...) y retorne audio_base64
    payload = {
        "text": "Yarbis, enciende la linterna",
        "session_id": "session_b64_test",
        "require_wake_word": False,
        "generate_audio": True,
        "include_audio_base64": True
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/command/process", json=payload)
        assert response.status_code == 200
        res = response.json()
        assert res["action_type"] == "device_control"
        assert res["audio_url"] is not None
        assert res["audio_url"].startswith("/api/v1/voice/audio/")
        assert res["audio_base64"] is not None
        assert len(res["audio_base64"]) > 0


@pytest.mark.asyncio
async def test_command_cancel_timer_and_set_reminder():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Cancelar temporizador
        res_timer = await ac.post("/api/v1/command/process", json={
            "text": "Yarbis, cancela el temporizador",
            "session_id": "test_timer_cancel",
            "require_wake_word": False,
            "generate_audio": False
        })
        assert res_timer.status_code == 200
        data_timer = res_timer.json()
        assert data_timer["action_type"] == "device_control"
        assert data_timer["command"] == "cancel_timer"

        # Recordatorio
        res_rem = await ac.post("/api/v1/command/process", json={
            "text": "Yarbis, pon un recordatorio de comprar leche",
            "session_id": "test_reminder_set",
            "require_wake_word": False,
            "generate_audio": False
        })
        assert res_rem.status_code == 200
        data_rem = res_rem.json()
        assert data_rem["action_type"] == "device_control"
        assert data_rem["command"] == "set_reminder"
        assert "leche" in data_rem["parameters"]["title"].lower()


@pytest.mark.asyncio
async def test_command_only_wake_word():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/command/process", json={
            "text": "Yarbis",
            "session_id": "test_only_wake",
            "require_wake_word": False,
            "generate_audio": False
        })
        assert res.status_code == 200
        data = res.json()
        assert data["action_type"] == "conversational_query"
        assert "¿a su orden?" in data["text_response"].lower() or "asistirle" in data["text_response"].lower()


@pytest.mark.asyncio
async def test_audio_endpoint_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/voice/audio/archivo_totalmente_inexistente.mp3")
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_command_catalog_all_device_controls():
    commands_to_test = [
        ("Yarbis, pon el brillo al 80%", "set_brightness", "level_percent", 80),
        ("Yarbis, sube el volumen al 70%", "set_volume", "level_percent", 70),
        ("Yarbis, activa el wifi", "toggle_wifi", "state", True),
        ("Yarbis, desactiva el wifi", "toggle_wifi", "state", False),
        ("Yarbis, activa el bluetooth", "toggle_bluetooth", "state", True),
        ("Yarbis, apaga el bluetooth", "toggle_bluetooth", "state", False),
        ("Yarbis, pon una alarma a las 7:00", "set_alarm", "time", "07:00"),
        ("Yarbis, cancela la alarma", "cancel_alarm", None, None),
        ("Yarbis, temporizador de 5 minutos", "set_timer", "duration_seconds", 300),
        ("Yarbis, abre Spotify", "open_app", "app_name", "Spotify"),
        ("Yarbis, llama a Carlos", "make_phone_call", "contact_name", "Carlos"),
        ("Yarbis, manda un whatsapp a Juan", "send_message", "recipient", "Carlos"),
        ("Yarbis, reproduce Queen en Spotify", "play_media", "platform", "spotify"),
        ("Yarbis, pon Bohemian Rhapsody en YouTube", "play_media", "platform", "youtube")
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for phrase, expected_cmd, param_key, param_val in commands_to_test:
            res = await ac.post("/api/v1/command/process", json={
                "text": phrase,
                "session_id": f"catalog_test_{expected_cmd}",
                "require_wake_word": False,
                "generate_audio": False
            })
            assert res.status_code == 200, f"Fallo en {phrase}: {res.text}"
            data = res.json()
            assert data["action_type"] == "device_control", f"Fallo action_type en {phrase}"
            assert data["command"] == expected_cmd, f"Fallo comando en {phrase}: esperado {expected_cmd}, obtenido {data['command']}"
            if param_key is not None and param_val is not None:
                assert data["parameters"].get(param_key) == param_val, f"Fallo parámetro en {phrase}: {data['parameters']}"


@pytest.mark.asyncio
async def test_real_m4a_voice_recognition_pipeline(tmp_path):
    """
    Prueba end-to-end con un archivo de audio .m4a (AAC) real generado por voz sintetizada.
    Comprueba que POST /api/v1/voice/process transcribe la voz real y extrae los parámetros dinámicos
    sin devolver comandos al azar.
    """
    import av
    from app.services.tts_service import EdgeTTSService

    tts = EdgeTTSService()
    mp3_path = tmp_path / "phrase.mp3"
    m4a_path = tmp_path / "phrase.m4a"
    await tts.synthesize("Yarbis, pon una alarma a las 8:30", mp3_path)

    with av.open(str(mp3_path)) as inp, av.open(str(m4a_path), "w", format="ipod") as out:
        in_stream = inp.streams.audio[0]
        out_stream = out.add_stream("aac", rate=44100)
        resampler = av.AudioResampler(format=out_stream.format, layout=out_stream.layout, rate=44100)
        for frame in inp.decode(in_stream):
            for rf in resampler.resample(frame):
                for packet in out_stream.encode(rf):
                    out.mux(packet)
        for packet in out_stream.encode(None):
            out.mux(packet)

    m4a_bytes = m4a_path.read_bytes()
    files = {
        "file": ("voice_input.m4a", m4a_bytes, "audio/m4a")
    }
    data = {
        "session_id": "real_voice_test",
        "require_wake_word": "true",
        "generate_audio": "false"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/v1/voice/process", files=files, data=data)
        assert res.status_code == 200
        body = res.json()
        assert body["action_type"] == "device_control"
        assert body["command"] == "set_alarm"
        assert body["parameters"]["time"] == "08:30"
        assert "8:30" in (body["transcription"] or "")


@pytest.mark.asyncio
async def test_session_memory_weather_followup():
    """
    Verifica que el backend almacena el historial atado al session_id
    y permite resolver preguntas de seguimiento ('¿y para mañana?')
    sin tener que repetir el sujeto de la conversación anterior.
    """
    session_id = "test_memory_session_weather"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turno 1: Preguntar por el clima en Monterrey
        turn1 = await ac.post(
            "/api/v1/command/process",
            json={
                "text": "¿Cómo está el clima en Monterrey?",
                "session_id": session_id,
                "require_wake_word": False,
                "generate_audio": False
            }
        )
        assert turn1.status_code == 200
        data1 = turn1.json()
        assert "Monterrey" in data1["text_response"]
        assert data1["action_type"] == "conversational_query"

        # Turno 2: Pregunta de seguimiento anafórica "¿y para mañana?"
        turn2 = await ac.post(
            "/api/v1/command/process",
            json={
                "text": "¿y para mañana?",
                "session_id": session_id,
                "require_wake_word": False,
                "generate_audio": False
            }
        )
        assert turn2.status_code == 200
        data2 = turn2.json()
        resp2 = data2["text_response"].lower()
        # Debe inferir automáticamente que se habla de Monterrey y de mañana
        assert "monterrey" in resp2
        assert "mañana" in resp2 or "pronostica" in resp2

        # Turno 3: Pregunta de seguimiento de entidad "¿y en París?"
        turn3 = await ac.post(
            "/api/v1/command/process",
            json={
                "text": "¿y en París?",
                "session_id": session_id,
                "require_wake_word": False,
                "generate_audio": False
            }
        )
        assert turn3.status_code == 200
        data3 = turn3.json()
        resp3 = data3["text_response"].lower()
        assert "parís" in resp3 or "paris" in resp3

        # Verificar endpoint de historial de sesión
        hist_res = await ac.get(f"/api/v1/session/{session_id}/history")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["session_id"] == session_id
        assert hist_data["turns_count"] == 3
        assert len(hist_data["messages"]) >= 6

        # Limpiar memoria de sesión
        del_res = await ac.delete(f"/api/v1/session/{session_id}")
        assert del_res.status_code == 200
        assert del_res.json()["cleared"] is True


@pytest.mark.asyncio
async def test_session_memory_device_followup():
    """
    Verifica que órdenes de ajuste de dispositivo ('cámbiala a las 8')
    utilizan el contexto de la orden previa en la sesión.
    """
    session_id = "test_memory_session_device"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turno 1: Poner alarma a las 7:00
        t1 = await ac.post(
            "/api/v1/command/process",
            json={
                "text": "Pon una alarma a las 7:00",
                "session_id": session_id,
                "require_wake_word": False,
                "generate_audio": False
            }
        )
        assert t1.status_code == 200
        assert t1.json()["parameters"]["time"] == "07:00"

        # Turno 2: Seguimiento sin repetir 'alarma'
        t2 = await ac.post(
            "/api/v1/command/process",
            json={
                "text": "Cámbiala a las 8:00",
                "session_id": session_id,
                "require_wake_word": False,
                "generate_audio": False
            }
        )
        assert t2.status_code == 200
        d2 = t2.json()
        assert d2["action_type"] == "device_control"
        assert d2["command"] == "set_alarm"
        assert d2["parameters"]["time"] == "08:00"
        assert "actualizada" in d2["text_response"].lower() or "08:00" in d2["text_response"]

