import pytest

from avaliacao import avaliar, normalizar_palavra, tokenizar


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
