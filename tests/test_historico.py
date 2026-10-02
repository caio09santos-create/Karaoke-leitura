from historico import media_pontos, ranking, recentes, salvar


class TestMediaPontos:
    def test_com_afinacao_tira_media(self):
        assert media_pontos(80, 60) == 70
        assert media_pontos(90, 70) == 80

    def test_sem_afinacao_usa_leitura(self):
        assert media_pontos(85, None) == 85


def test_salvar_e_recentes(tmp_path):
    db = str(tmp_path / "h.sqlite3")
    salvar("Ana", "A", "T1", 80, 70, 8, 10, db_path=db, quando="2026-01-01T10:00:00")
    salvar("Bia", "B", "T2", 60, None, 6, 10, db_path=db, quando="2026-01-01T11:00:00")
    r = recentes(db_path=db)
    assert [x["cantor"] for x in r] == ["Bia", "Ana"]  # mais recente primeiro
    assert r[0]["media"] == 60  # sem afinação -> só leitura


def test_ranking_ordena_por_media(tmp_path):
    db = str(tmp_path / "h.sqlite3")
    salvar("Ana", "A", "T", 50, 50, 5, 10, db_path=db, quando="2026-01-01T10:00:00")
    salvar("Bia", "B", "T", 90, 90, 9, 10, db_path=db, quando="2026-01-01T10:01:00")
    salvar("Cae", "C", "T", 70, None, 7, 10, db_path=db, quando="2026-01-01T10:02:00")
    rk = ranking(db_path=db)
    assert [x["cantor"] for x in rk] == ["Bia", "Cae", "Ana"]  # 90, 70, 50
