# Atalhos do projeto. Uso: `make <alvo>` (ex.: make check)
# Requer um ambiente virtual ativo (veja `make venv`).

.PHONY: help venv install test lint format check run

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

venv:  ## Cria o ambiente virtual em .venv
	python3 -m venv .venv
	@echo "Agora rode: source .venv/bin/activate && make install"

install:  ## Instala as dependências de desenvolvimento
	pip install -r requirements-dev.txt

test:  ## Roda os testes (pytest)
	pytest

lint:  ## Verifica o código (ruff)
	ruff check .

format:  ## Formata o código (ruff format)
	ruff format .

check: lint test  ## Roda lint + testes (use antes de commitar)

run:  ## Sobe o app Streamlit
	streamlit run app.py
