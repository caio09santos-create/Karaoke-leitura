# 🎤 Karaoke-leitura

App de karaokê que dá uma **nota** para o quanto você acertou a letra ao cantar.

Você escolhe a música, busca (ou cola) a letra, grava sua voz pelo microfone e o
app transcreve o áudio com **Whisper**, compara com a letra e devolve uma nota de
0 a 100 destacando as palavras certas (verde) e erradas (vermelho).

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `app.py` | Interface Streamlit e reconhecimento de voz (faster-whisper) |
| `letras.py` | Busca de letras na API pública do [LRCLIB](https://lrclib.net) |
| `avaliacao.py` | Tokenização e cálculo da nota (difflib + rapidfuzz) |
| `tests/` | Testes unitários (pytest) |

## Requisitos

- Python 3.10+

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Para desenvolver (testes e lint):

```bash
pip install -r requirements-dev.txt
```

> Na primeira execução o modelo de voz do Whisper é baixado automaticamente.

## Executar

```bash
streamlit run app.py
```

Dica: use **fones de ouvido** ao gravar — se o microfone captar a música, a voz do
cantor original é contada como sua.

## Testes

```bash
pytest
```

Os testes cobrem só a lógica (`avaliacao.py` e `letras.py`) e não importam `app.py`,
então rodam com um conjunto enxuto de dependências (`requirements-test.txt`) — sem
precisar de `streamlit`/`faster-whisper`. É isso que o CI usa.

## CI

O GitHub Actions (`.github/workflows/ci.yml`) roda `ruff check` + `pytest` a cada
push e pull request, instalando apenas `requirements-test.txt`.

## Lint / formatação

```bash
ruff check .      # verifica
ruff check --fix .  # corrige o que der
ruff format .     # formata
```

## Atalhos (Makefile)

Para não decorar os comandos, há um `Makefile`:

```bash
make          # lista os atalhos disponíveis
make venv     # cria o ambiente virtual em .venv
make install  # instala as dependências de desenvolvimento
make test     # roda os testes
make lint     # roda o ruff
make format   # formata o código
make check    # lint + testes (rode antes de commitar)
make run      # sobe o app Streamlit
```

Fluxo típico do zero:

```bash
make venv
source .venv/bin/activate
make install
make check
```
