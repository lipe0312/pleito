from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")


class ConfiguracaoBancoInvalida(RuntimeError):
    pass


def validar_destino(host: str, port: int, dbname: str) -> None:
    if host not in {"127.0.0.1", "localhost"} or port != 55432:
        raise ConfiguracaoBancoInvalida("conexao recusada fora do Postgres isolado do pleito")
    if dbname != "pleito":
        raise ConfiguracaoBancoInvalida("conexao recusada fora do banco pleito")


def conectar(componente: str) -> psycopg.Connection:
    variaveis = {
        "app": ("pleito_app_login", "POSTGRES_APP_PASSWORD"),
        "painel": ("pleito_painel_login", "POSTGRES_PANEL_PASSWORD"),
    }
    if componente not in variaveis:
        raise ValueError("componente de banco desconhecido")
    usuario, variavel_senha = variaveis[componente]
    valores = {
        "host": os.getenv("POSTGRES_HOST"),
        "port": os.getenv("POSTGRES_PORT"),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": usuario,
        "password": os.getenv(variavel_senha),
    }
    if any(not valor for valor in valores.values()):
        raise ConfiguracaoBancoInvalida("configuracao de conexao do banco incompleta")
    try:
        valores["port"] = int(valores["port"])
    except ValueError as exc:
        raise ConfiguracaoBancoInvalida("POSTGRES_PORT precisa ser numerica") from exc
    validar_destino(valores["host"], valores["port"], valores["dbname"])
    return psycopg.connect(**valores)
