import letras
from letras import (
    _extrair_letra,
    buscar_letra,
    buscar_letra_sincronizada,
    parse_lrc,
    remover_tempos_lrc,
)


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


class TestParseLrc:
    def test_converte_tempo_para_segundos(self):
        entrada = "[00:12.34]primeira\n[01:05.00]segunda"
        assert parse_lrc(entrada) == [(12.34, "primeira"), (65.0, "segunda")]

    def test_fracao_de_tres_digitos_e_milissegundos(self):
        assert parse_lrc("[00:01.500]x") == [(1.5, "x")]

    def test_ignora_linha_sem_marcacao(self):
        assert parse_lrc("sem tempo\n[00:02.00]com") == [(2.0, "com")]

    def test_ignora_linha_sem_texto(self):
        assert parse_lrc("[00:01.00]\n[00:02.00]canta") == [(2.0, "canta")]


def _get_search(get_resp, search_resp):
    """Cria um fake de requests.get que responde por endpoint (/get vs /search)."""

    def fake_get(url, **kwargs):
        return get_resp if url.endswith("/get") else search_resp

    return fake_get


class TestBuscarLetraSincronizada:
    def test_synced_com_nomes_canonicos(self, monkeypatch):
        get_resp = _FakeResp(
            200,
            {
                "syncedLyrics": "[00:01.00]a\n[00:02.00]b",
                "artistName": "Artista Real",
                "trackName": "Faixa Real",
            },
        )
        monkeypatch.setattr(letras.requests, "get", _get_search(get_resp, _FakeResp(200, [])))
        dados = buscar_letra_sincronizada("chute", "trocado")
        assert dados == {
            "plain": "a\nb",
            "synced": [(1.0, "a"), (2.0, "b")],
            "artista": "Artista Real",
            "titulo": "Faixa Real",
        }

    def test_so_plain_usa_termos_passados_como_fallback(self, monkeypatch):
        get_resp = _FakeResp(200, {"plainLyrics": "a\nb"})
        monkeypatch.setattr(letras.requests, "get", _get_search(get_resp, _FakeResp(200, [])))
        dados = buscar_letra_sincronizada("Artista", "Titulo")
        assert dados == {"plain": "a\nb", "synced": None, "artista": "Artista", "titulo": "Titulo"}

    def test_prefere_resultado_com_sincronizada(self, monkeypatch):
        # /get sem letra; a busca traz um só-plain e um sincronizado -> escolhe o sincronizado
        get_resp = _FakeResp(404, None)
        search_resp = _FakeResp(
            200,
            [
                {"plainLyrics": "x", "artistName": "P", "trackName": "Q"},
                {"syncedLyrics": "[00:03.00]c", "artistName": "S", "trackName": "T"},
            ],
        )
        monkeypatch.setattr(letras.requests, "get", _get_search(get_resp, search_resp))
        dados = buscar_letra_sincronizada("a", "b")
        assert dados["synced"] == [(3.0, "c")]
        assert (dados["artista"], dados["titulo"]) == ("S", "T")

    def test_instrumental_sem_resultado_retorna_none(self, monkeypatch):
        get_resp = _FakeResp(200, {"instrumental": True})
        monkeypatch.setattr(letras.requests, "get", _get_search(get_resp, _FakeResp(200, [])))
        assert buscar_letra_sincronizada("Artista", "Titulo") is None

    def test_erro_de_rede_retorna_none(self, monkeypatch):
        def fake_get(url, **kwargs):
            raise letras.requests.RequestException("sem rede")

        monkeypatch.setattr(letras.requests, "get", fake_get)
        assert buscar_letra_sincronizada("Artista", "Titulo") is None
