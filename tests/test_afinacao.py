import numpy as np

from afinacao import desvio_cents, extrair_f0, nota_afinacao

SR = 16000


def _senoide(freq, dur=1.0, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _senoide_cents(base=440.0, cents=0.0, dur=1.0, sr=SR):
    """Senoide `cents` acima/abaixo de `base` (constante)."""
    return _senoide(base * 2 ** (cents / 1200.0), dur=dur, sr=sr)


def _vibrato(base=440.0, cents_amp=40.0, taxa_hz=5.5, dur=1.5, sr=SR):
    """Senoide com vibrato: oscila ±`cents_amp` cents em torno de `base`."""
    t = np.arange(int(dur * sr)) / sr
    freq = base * 2 ** ((cents_amp * np.sin(2 * np.pi * taxa_hz * t)) / 1200.0)
    fase = 2 * np.pi * np.cumsum(freq) / sr
    return np.sin(fase).astype(np.float32)


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

    def test_vibrato_nao_penaliza(self):
        # vibrato ±40 cents em torno da nota: a mediana por nota deve manter nota alta
        assert nota_afinacao(extrair_f0(_vibrato(cents_amp=40.0)))["nota"] > 80

    def test_pct_afinado_alto_quando_afinado(self):
        assert nota_afinacao(extrair_f0(_senoide(440.0)))["pct_afinado"] > 0.8

    def test_tendencia_detecta_agudo(self):
        assert nota_afinacao(extrair_f0(_senoide_cents(cents=30.0)))["tendencia"] > 20

    def test_tendencia_detecta_grave(self):
        assert nota_afinacao(extrair_f0(_senoide_cents(cents=-30.0)))["tendencia"] < -20
