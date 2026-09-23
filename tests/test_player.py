from player import construir_player_sincronizado


class TestConstruirPlayer:
    def test_inclui_dados_no_html(self):
        html = construir_player_sincronizado([(1.0, "sol"), (2.5, "lua")])
        assert "const LINHAS =" in html
        assert '"sol"' in html and '"lua"' in html
        assert "1.0" in html and "2.5" in html

    def test_altura_e_atraso_aplicados(self):
        html = construir_player_sincronizado([(0.0, "x")], altura=500, atraso=1.5)
        assert "500px" in html
        assert "let atraso = 1.5" in html
        assert 'value="1.5"' in html

    def test_escapa_fechamento_de_script(self):
        payload = "</script><script>alert(1)</script>"
        html = construir_player_sincronizado([(0.0, payload)])
        # A injeção crua não pode aparecer; o `</` tem de estar escapado.
        assert payload not in html
        assert "<\\/script><script>alert(1)<\\/script>" in html

    def test_sem_synced_retorna_aviso(self):
        html = construir_player_sincronizado([])
        assert "Sem letra sincronizada" in html
