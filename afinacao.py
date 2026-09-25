"""Nota de afinação (intonação) a partir da gravação, sem melodia de referência.

Mede o quão centrado nas notas da escala temperada a pessoa canta: para os trechos
com voz, quanto menor o desvio em cents da nota mais próxima, maior a nota. Usa numpy
puro para a detecção de pitch (autocorrelação) e PyAV (import preguiçoso) só para
decodificar o áudio gravado. Não verifica se a melodia da música foi seguida.
"""

import numpy as np

SR = 16000


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
    tam = 1024
    passo = 256
    lag_min = max(1, int(sr / fmax))
    lag_max = min(tam - 1, int(sr / fmin))
    f0 = []
    for ini in range(0, len(samples) - tam, passo):
        quadro = samples[ini : ini + tam].astype(np.float64)
        quadro = quadro - quadro.mean()
        energia = np.dot(quadro, quadro)
        if energia < 1e-6:  # silêncio
            f0.append(np.nan)
            continue
        corr = np.correlate(quadro, quadro, mode="full")[tam - 1 :]
        janela = corr[lag_min : lag_max + 1]
        if janela.size == 0:
            f0.append(np.nan)
            continue
        pico = int(np.argmax(janela)) + lag_min
        # razão do pico sobre a energia = confiança de periodicidade (voz)
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


def nota_afinacao(f0: np.ndarray, min_voz: int = 20) -> dict:
    """Calcula a nota de afinação a partir do f0 por quadro.

    Retorna {nota, cents_medio, voz_frac}. `nota` é None quando há voz de menos.
    """
    f0 = np.asarray(f0, dtype=np.float64)
    total = f0.size
    voz = f0[np.isfinite(f0) & (f0 > 0)]
    voz_frac = (voz.size / total) if total else 0.0
    if voz.size < min_voz:
        return {"nota": None, "cents_medio": None, "voz_frac": voz_frac}
    cents_abs = np.abs(desvio_cents(voz))
    mediana = float(np.median(cents_abs))
    # 0 cents -> 100 ; 50 cents (quarto de tom, pior caso) -> 0
    nota = int(round(max(0.0, min(100.0, 100.0 * (1.0 - mediana / 50.0)))))
    return {"nota": nota, "cents_medio": round(mediana, 1), "voz_frac": round(voz_frac, 2)}


def avaliar_afinacao(audio_bytes: bytes) -> dict | None:
    """Decodifica a gravação e devolve a nota de afinação, ou None em caso de falha."""
    try:
        samples = _decodificar_pcm(audio_bytes)
    except Exception:
        return None
    resultado = nota_afinacao(extrair_f0(samples))
    return resultado if resultado["nota"] is not None else None
