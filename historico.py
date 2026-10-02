"""Histórico e placar das apresentações, persistidos em SQLite (stdlib sqlite3).

Sem dependências novas. Abre uma conexão por chamada (evita problemas de thread do
Streamlit). O caminho do banco é injetável para testes.
"""

import os
import sqlite3
from datetime import datetime

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico.sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS apresentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    cantor TEXT NOT NULL,
    artista TEXT,
    titulo TEXT,
    nota_leitura INTEGER NOT NULL,
    afinacao INTEGER,
    acertos INTEGER,
    total INTEGER,
    media REAL NOT NULL
)
"""


def media_pontos(nota_leitura: int, afinacao: int | None) -> int:
    """Média de leitura + afinação; só leitura quando não há afinação."""
    if afinacao is None:
        return int(nota_leitura)
    return round((nota_leitura + afinacao) / 2)


def _conectar(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def salvar(
    cantor: str,
    artista: str,
    titulo: str,
    nota_leitura: int,
    afinacao: int | None,
    acertos: int,
    total: int,
    *,
    db_path: str = _DB,
    quando: str | None = None,
) -> None:
    """Salva uma apresentação no histórico."""
    data = quando or datetime.now().isoformat(timespec="seconds")
    with _conectar(db_path) as conn:
        conn.execute(
            "INSERT INTO apresentacoes (data, cantor, artista, titulo, nota_leitura, "
            "afinacao, acertos, total, media) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data,
                cantor or "Convidado",
                artista,
                titulo,
                int(nota_leitura),
                afinacao,
                acertos,
                total,
                media_pontos(nota_leitura, afinacao),
            ),
        )


def recentes(limite: int = 15, *, db_path: str = _DB) -> list[dict]:
    """Apresentações mais recentes primeiro."""
    with _conectar(db_path) as conn:
        linhas = conn.execute(
            "SELECT * FROM apresentacoes ORDER BY data DESC, id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def ranking(limite: int = 10, *, db_path: str = _DB) -> list[dict]:
    """Melhores apresentações por média (desempate pela nota de leitura)."""
    with _conectar(db_path) as conn:
        linhas = conn.execute(
            "SELECT * FROM apresentacoes ORDER BY media DESC, nota_leitura DESC, id ASC "
            "LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(linha) for linha in linhas]
