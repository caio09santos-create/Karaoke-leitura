"""Compara a transcrição do canto com a letra e calcula a nota."""

import re
import unicodedata
from difflib import SequenceMatcher

from rapidfuzz import fuzz


def normalizar_palavra(palavra: str) -> str:
    """Minúsculas, sem acentos e sem pontuação: 'Coração,' -> 'coracao'."""
    palavra = unicodedata.normalize("NFKD", palavra.lower())
    palavra = "".join(c for c in palavra if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", palavra)


def tokenizar(texto: str) -> list[tuple[int, str, str]]:
    """Retorna (número da linha, palavra original, palavra normalizada)."""
    tokens = []
    for n_linha, linha in enumerate(texto.splitlines()):
        # Remove marcações como [Refrão] ou (2x)
        linha = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", linha)
        linha = linha.replace("-", " ")
        for palavra in linha.split():
            normal = normalizar_palavra(palavra)
            if normal:
                tokens.append((n_linha, palavra, normal))
    return tokens


def avaliar(
    letra: str,
    transcricao: str,
    limiar_semelhanca: int = 80,
    acerto_para_nota_maxima: float = 0.85,
) -> dict:
    """
    Compara palavra a palavra.

    - limiar_semelhanca: palavras com semelhança >= esse valor (0-100)
      contam como acerto (tolera pequenos erros do reconhecimento de voz).
    - acerto_para_nota_maxima: taxa de acerto que já vale nota 100,
      porque o reconhecimento de voz cantada nunca é perfeito.
    """
    tokens_letra = tokenizar(letra)
    if not tokens_letra:
        raise ValueError("A letra está vazia.")

    ref = [t[2] for t in tokens_letra]
    hip = [t[2] for t in tokenizar(transcricao)]

    acertos = [False] * len(ref)
    comparador = SequenceMatcher(None, ref, hip, autojunk=False)
    for tag, i1, i2, j1, j2 in comparador.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                acertos[i] = True
        elif tag == "replace":
            for desloc, i in enumerate(range(i1, i2)):
                j = j1 + desloc
                if j < j2 and fuzz.ratio(ref[i], hip[j]) >= limiar_semelhanca:
                    acertos[i] = True

    total_acertos = sum(acertos)
    taxa = total_acertos / len(ref)
    nota = min(100, round(taxa / acerto_para_nota_maxima * 100))

    palavras = [
        (n_linha, original, acertou)
        for (n_linha, original, _), acertou in zip(tokens_letra, acertos)
    ]
    return {
        "nota": nota,
        "taxa": taxa,
        "acertos": total_acertos,
        "total": len(ref),
        "palavras": palavras,
    }