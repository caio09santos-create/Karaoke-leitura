import sys
import types

from audio import _mimetype_por_ext, _opcoes_ydl, baixar_audio


class TestMimetype:
    def test_conhecidos(self):
        assert _mimetype_por_ext("m4a") == "audio/mp4"
        assert _mimetype_por_ext(".webm") == "audio/webm"
        assert _mimetype_por_ext("MP3") == "audio/mpeg"

    def test_desconhecido_usa_fallback(self):
        assert _mimetype_por_ext("xyz") == "audio/mpeg"


class TestOpcoesYdl:
    def test_formato_e_flags(self):
        opts = _opcoes_ydl("/tmp/pasta")
        assert "bestaudio" in opts["format"]
        assert opts["noplaylist"] is True
        assert opts["quiet"] is True
        assert opts["outtmpl"].startswith("/tmp/pasta")
        assert opts["outtmpl"].endswith("audio.%(ext)s")


def _fake_yt_dlp(escreve_ext="m4a", erro=False):
    """Módulo yt_dlp falso; download escreve <pasta>/audio.<ext> ou levanta erro."""
    mod = types.ModuleType("yt_dlp")

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            if erro:
                raise RuntimeError("falhou")
            caminho = self.opts["outtmpl"].replace("%(ext)s", escreve_ext)
            with open(caminho, "wb") as arquivo:
                arquivo.write(b"FAKE-AUDIO")

    mod.YoutubeDL = FakeYDL
    return mod


class TestBaixarAudio:
    def test_download_feliz_retorna_bytes_e_mime(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "yt_dlp", _fake_yt_dlp(escreve_ext="m4a"))
        assert baixar_audio("http://exemplo/x") == (b"FAKE-AUDIO", "audio/mp4")

    def test_webm_mapeia_para_audio_webm(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "yt_dlp", _fake_yt_dlp(escreve_ext="webm"))
        dados, mime = baixar_audio("http://exemplo/x")
        assert dados == b"FAKE-AUDIO" and mime == "audio/webm"

    def test_erro_no_download_retorna_none(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "yt_dlp", _fake_yt_dlp(erro=True))
        assert baixar_audio("http://exemplo/x") is None

    def test_sem_yt_dlp_instalado_retorna_none(self, monkeypatch):
        # Entrada None em sys.modules faz `import yt_dlp` levantar ImportError.
        monkeypatch.setitem(sys.modules, "yt_dlp", None)
        assert baixar_audio("http://exemplo/x") is None
