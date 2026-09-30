import numpy as np

from afinacao import desvio_cents, extrair_f0, nota_afinacao

SR = 16000


def _senoide(freq, dur=1.0, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


class TestExtrairF0:
    def test_detecta_frequencia_da_senoide(self):
        f0 = extrair_f0(_senoide(220.0))
        voz = f0[np.isfinite(f0)]
        assert voz.size > 0
        assert abs(float(np.median(voz)) - 220.0) < 5.0

    def test_silencio_nao_tem_voz(self):
        f0 = extrair_f0(np.zeros(SR, dtype=np.float32))
        assert f0[np.isfinite(f0)].size == 0

    def test_senoide_afinada_da_nota_alta(self):
        # 440 Hz puro deve pontuar alto (depende da interpolação sub-amostral do pico)
        assert nota_afinacao(extrair_f0(_senoide(440.0)))["nota"] > 85


class TestDesvioCents:
    def test_a440_perto_de_zero(self):
        assert abs(float(desvio_cents(np.array([440.0]))[0])) < 1.0

    def test_quarto_de_tom_50_cents(self):
        f = 440.0 * 2 ** (0.5 / 12)  # meio semitom acima = +50 cents
        assert abs(abs(float(desvio_cents(np.array([f]))[0])) - 50.0) < 2.0


class TestNotaAfinacao:
    def test_afinado_da_nota_alta(self):
        assert nota_afinacao(np.full(200, 440.0))["nota"] > 90

    def test_desafinado_da_nota_baixa(self):
        f0 = np.full(200, 440.0 * 2 ** (0.5 / 12))  # +50 cents constante
        assert nota_afinacao(f0)["nota"] < 20

    def test_pouca_voz_retorna_none(self):
        f0 = np.array([np.nan] * 5 + [440.0] * 3)
        assert nota_afinacao(f0)["nota"] is None
