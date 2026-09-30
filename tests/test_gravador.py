import base64

from gravador import _decode_gravacao


class TestDecodeGravacao:
    def test_base64_valido_retorna_bytes_e_mime(self):
        dados = b"AUDIO-BYTES"
        valor = {"audio_b64": base64.b64encode(dados).decode(), "mime": "audio/webm"}
        assert _decode_gravacao(valor) == (dados, "audio/webm")

    def test_mime_padrao_quando_ausente(self):
        valor = {"audio_b64": base64.b64encode(b"x").decode()}
        assert _decode_gravacao(valor) == (b"x", "audio/webm")

    def test_nao_dict_retorna_none(self):
        assert _decode_gravacao(None) is None
        assert _decode_gravacao("x") is None
        assert _decode_gravacao(123) is None

    def test_sem_audio_ou_vazio_retorna_none(self):
        assert _decode_gravacao({}) is None
        assert _decode_gravacao({"audio_b64": ""}) is None

    def test_base64_invalido_retorna_none(self):
        assert _decode_gravacao({"audio_b64": "@@@nao-base64@@@"}) is None
