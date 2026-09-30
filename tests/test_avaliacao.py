import pytest

from avaliacao import avaliar, normalizar_palavra, resumo_por_linha, tokenizar


class TestNormalizarPalavra:
    def test_remove_acentos_pontuacao_e_caixa(self):
        assert normalizar_palavra("Coração,") == "coracao"

    def test_mantem_numeros(self):
        assert normalizar_palavra("2Pac!") == "2pac"

    def test_so_pontuacao_vira_vazio(self):
        assert normalizar_palavra("...!") == ""


class TestTokenizar:
    def test_ignora_marcacoes_de_secao_e_repeticao(self):
        tokens = tokenizar("[Refrão] canta (2x)")
        normais = [t[2] for t in tokens]
        assert normais == ["canta"]

    def test_separa_hifen_e_guarda_numero_da_linha(self):
        tokens = tokenizar("bem-vindo\namigo")
        # (n_linha, original, normal)
        assert tokens[0][0] == 0 and tokens[1][0] == 0  # "bem", "vindo" na linha 0
        assert tokens[2][0] == 1  # "amigo" na linha 1
        assert [t[2] for t in tokens] == ["bem", "vindo", "amigo"]


class TestAvaliar:
    def test_letra_vazia_levanta_erro(self):
        with pytest.raises(ValueError):
            avaliar("", "qualquer coisa")

    def test_acerto_total_da_nota_maxima(self):
        letra = "amor eterno"
        resultado = avaliar(letra, "amor eterno")
        assert resultado["nota"] == 100
        assert resultado["acertos"] == resultado["total"] == 2
        assert resultado["taxa"] == 1.0

    def test_zero_acertos_da_nota_zero(self):
        resultado = avaliar("amor eterno", "batata frita")
        assert resultado["nota"] == 0
        assert resultado["acertos"] == 0

    def test_tolera_pequeno_erro_de_reconhecimento(self):
        # "coracao" vs "coracaum": semelhança alta -> conta como acerto
        resultado = avaliar("meu coracao", "meu coracaum")
        assert resultado["acertos"] == 2

    def test_marca_palavra_a_palavra_com_numero_de_linha(self):
        resultado = avaliar("sol\nlua", "sol xxxx")
        palavras = resultado["palavras"]  # [(n_linha, original, acertou), ...]
        assert palavras[0] == (0, "sol", True)
        assert palavras[1] == (1, "lua", False)

    def test_mantem_chaves_antigas_e_adiciona_por_linha(self):
        resultado = avaliar("amor eterno", "amor eterno")
        assert {"nota", "taxa", "acertos", "total", "palavras", "por_linha"} <= set(
            resultado
        )


class TestResumoPorLinha:
    def test_agrega_acertos_e_texto_por_linha(self):
        resultado = avaliar("sol forte\nlua cheia", "sol forte xxxx yyyy")
        por_linha = resultado["por_linha"]
        assert por_linha[0]["texto"] == "sol forte"
        assert por_linha[0]["acertos"] == 2 and por_linha[0]["total"] == 2
        assert por_linha[0]["taxa"] == 1.0
        assert por_linha[1]["acertos"] == 0 and por_linha[1]["taxa"] == 0.0

    def test_tempo_cantado_e_a_mediana_dos_tempos_da_linha(self):
        tempos = [("sol", 10.0), ("forte", 12.0), ("lua", 30.0), ("cheia", 34.0)]
        resultado = avaliar("sol forte\nlua cheia", "sol forte lua cheia", hipotese_tempos=tempos)
        por_linha = resultado["por_linha"]
        assert por_linha[0]["tempo_cantado"] == 11.0  # mediana(10, 12)
        assert por_linha[1]["tempo_cantado"] == 32.0  # mediana(30, 34)

    def test_sem_tempos_o_tempo_cantado_e_none(self):
        resultado = avaliar("sol forte", "sol forte")
        assert resultado["por_linha"][0]["tempo_cantado"] is None

    def test_funcao_isolada_com_dados_sinteticos(self):
        tokens = [(0, "Sol", "sol"), (0, "forte", "forte"), (1, "Lua", "lua")]
        acertos = [True, True, False]
        tempos_por_ref = [5.0, 7.0, None]
        resumo = resumo_por_linha(tokens, acertos, tempos_por_ref)
        assert resumo[0] == {
            "linha": 0,
            "texto": "Sol forte",
            "palavras": [("Sol", True), ("forte", True)],
            "acertos": 2,
            "total": 2,
            "taxa": 1.0,
            "tempo_cantado": 6.0,
        }
        assert resumo[1]["tempo_cantado"] is None and resumo[1]["acertos"] == 0
