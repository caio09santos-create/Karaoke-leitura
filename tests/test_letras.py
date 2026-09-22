import letras
from letras import _extrair_letra, buscar_letra, remover_tempos_lrc


class TestRemoverTemposLrc:
    def test_remove_marcacoes_de_tempo(self):
        entrada = "[00:12.34]primeira linha\n[00:15.00]segunda linha"
        assert remover_tempos_lrc(entrada) == "primeira linha\nsegunda linha"

    def test_descarta_linhas_vazias(self):
        entrada = "[00:01.00]\n[00:02.00]canta"
        assert remover_tempos_lrc(entrada) == "canta"


class TestExtrairLetra:
    def test_instrumental_retorna_none(self):
        assert _extrair_letra({"instrumental": True, "plainLyrics": "x"}) is None

    def test_prefere_plain_lyrics(self):
        assert _extrair_letra({"plainLyrics": "  olá mundo  "}) == "olá mundo"

    def test_usa_synced_quando_nao_ha_plain(self):
        dados = {"syncedLyrics": "[00:01.00]linha unica"}
        assert _extrair_letra(dados) == "linha unica"

    def test_sem_letra_retorna_none(self):
        assert _extrair_letra({}) is None


class _FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class TestBuscarLetra:
    def test_retorna_letra_na_busca_exata(self, monkeypatch):
        def fake_get(url, **kwargs):
            return _FakeResp(200, {"plainLyrics": "linha um\nlinha dois"})

        monkeypatch.setattr(letras.requests, "get", fake_get)
        assert buscar_letra("Artista", "Titulo") == "linha um\nlinha dois"

    def test_erro_de_rede_retorna_none(self, monkeypatch):
        def fake_get(url, **kwargs):
            raise letras.requests.RequestException("sem rede")

        monkeypatch.setattr(letras.requests, "get", fake_get)
        assert buscar_letra("Artista", "Titulo") is None
