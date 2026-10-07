"""Nota de afinação (intonação) a partir da gravação, sem melodia de referência.

Detecta o pitch (autocorrelação em numpy, PyAV só para decodificar), agrupa os
quadros em notas sustentadas e mede, por nota, o desvio em cents da nota temperada
mais próxima. Trabalhar por nota (mediana) absorve o vibrato e ignora transições.
Não verifica se a melodia da música foi seguida.
"""

import numpy as np

SR = 16000
_TAM = 1024
_PASSO = 256
_HOP_S = _PASSO / SR


def _decodificar_pcm(audio_bytes: bytes, sr: int = SR) -> np.ndarray:
    """Decodifica a gravação (webm/m4a/...) em mono float32 reamostrado para `sr`."""
    import io

    import av

    with av.open(io.BytesIO(audio_bytes)) as container:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
        pedacos = []
        for frame in container.decode(audio=0):
            for saida in resampler.resample(frame):
                pedacos.append(saida.to_ndarray().reshape(-1))
    if not pedacos:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(pedacos).astype(np.float32)


def extrair_f0(
    samples: np.ndarray,
    sr: int = SR,
    fmin: float = 80.0,
    fmax: float = 1000.0,
    limiar_voz: float = 0.30,
) -> np.ndarray:
    """f0 (Hz) por quadro via autocorrelação; NaN nos quadros sem voz."""
    if samples.size == 0:
        return np.zeros(0, dtype=np.float32)
    lag_min = max(1, int(sr / fmax))
    lag_max = min(_TAM - 1, int(sr / fmin))
    f0 = []
    for ini in range(0, len(samples) - _TAM, _PASSO):
        quadro = samples[ini : ini + _TAM].astype(np.float64)
        quadro = quadro - quadro.mean()
        energia = np.dot(quadro, quadro)
        if energia < 1e-6:  # silêncio
            f0.append(np.nan)
            continue
        corr = np.correlate(quadro, quadro, mode="full")[_TAM - 1 :]
        janela = corr[lag_min : lag_max + 1]
        if janela.size == 0:
            f0.append(np.nan)
            continue
        pico = int(np.argmax(janela)) + lag_min
        if corr[pico] / energia < limiar_voz:
            f0.append(np.nan)
            continue
        # interpolação parabólica no pico -> lag sub-amostral (precisão em cents)
        lag = float(pico)
        if 0 < pico < corr.size - 1:
            a, b, c = corr[pico - 1], corr[pico], corr[pico + 1]
            denom = a - 2.0 * b + c
            if denom != 0:
                lag = pico + 0.5 * (a - c) / denom
        f0.append(sr / lag)
    return np.array(f0, dtype=np.float32)


def desvio_cents(f0_hz: np.ndarray) -> np.ndarray:
    """Desvio (em cents) de cada f0 para a nota temperada mais próxima (A440)."""
    f0_hz = np.asarray(f0_hz, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        midi = 69.0 + 12.0 * np.log2(f0_hz / 440.0)
    return (midi - np.round(midi)) * 100.0


def _para_midi(f0: np.ndarray) -> np.ndarray:
    """Converte f0 (Hz) em número MIDI; NaN onde não há voz."""
    f0 = np.asarray(f0, dtype=np.float64)
    valido = np.isfinite(f0) & (f0 > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(valido, 69.0 + 12.0 * np.log2(np.where(valido, f0, 1.0) / 440.0), np.nan)


def _segmentar(f0: np.ndarray, min_frames: int = 6, tol_semitom: float = 0.7):
    """Agrupa quadros com voz em notas sustentadas.

    Retorna (segmentos, alvo_por_frame): `segmentos` é a lista de arrays de MIDI de
    cada nota; `alvo_por_frame` tem a nota arredondada por quadro (NaN fora de nota).
    Começa nova nota quando há lacuna sem voz ou salto > `tol_semitom` da mediana.
    """
    midi = _para_midi(f0)
    alvo = np.full(midi.size, np.nan)
    segmentos: list[np.ndarray] = []
    atual: list[int] = []

    def fechar():
        if len(atual) >= min_frames:
            vals = midi[atual]
            segmentos.append(vals)
            alvo[atual] = round(float(np.median(vals)))

    for i, m in enumerate(midi):
        if np.isnan(m):
            fechar()
            atual = []
            continue
        if atual and abs(m - np.median(midi[atual])) > tol_semitom:
            fechar()
            atual = []
        atual.append(i)
    fechar()
    return segmentos, alvo


def nota_afinacao(f0: np.ndarray) -> dict:
    """Nota de afinação por nota sustentada (mediana vs nota mais próxima).

    Retorna {nota, cents_medio, voz_frac, pct_afinado, tendencia}. `nota` é None
    quando não há notas sustentadas suficientes.
    """
    total = int(np.asarray(f0).size)
    segmentos, _ = _segmentar(f0)
    voz = sum(int(s.size) for s in segmentos)
    voz_frac = round(voz / total, 2) if total else 0.0
    if not segmentos:
        return {
            "nota": None,
            "cents_medio": None,
            "voz_frac": voz_frac,
            "pct_afinado": 0.0,
            "tendencia": None,
        }

    cents_abs, cents_sig, pesos = [], [], []
    dur_total = dur_afinado = 0
    for s in segmentos:
        med = float(np.median(s))
        desvio = (med - round(med)) * 100.0
        cents_abs.append(abs(desvio))
        cents_sig.append(desvio)
        pesos.append(s.size)
        dur_total += s.size
        if abs(desvio) <= 25:
            dur_afinado += s.size

    pesos_arr = np.array(pesos, dtype=float)
    cents_medio = float(np.average(cents_abs, weights=pesos_arr))
    tendencia = float(np.average(cents_sig, weights=pesos_arr))
    nota = int(round(max(0.0, min(100.0, 100.0 * (1.0 - cents_medio / 50.0)))))
    return {
        "nota": nota,
        "cents_medio": round(cents_medio, 1),
        "voz_frac": voz_frac,
        "pct_afinado": round(dur_afinado / dur_total, 2) if dur_total else 0.0,
        "tendencia": round(tendencia, 1),
    }


def avaliar_afinacao(audio_bytes: bytes) -> dict | None:
    """Decodifica a gravação e devolve a nota de afinação + série do gráfico, ou None."""
    try:
        samples = _decodificar_pcm(audio_bytes)
    except Exception:
        return None
    f0 = extrair_f0(samples)
    resultado = nota_afinacao(f0)
    if resultado["nota"] is None:
        return None
    _, alvo = _segmentar(f0)
    midi = _para_midi(f0)
    resultado["serie"] = {
        "Você": [None if np.isnan(x) else round(float(x), 2) for x in midi],
        "Nota alvo": [None if np.isnan(x) else float(x) for x in alvo],
    }
    return resultado
