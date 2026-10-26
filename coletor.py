
import requests
import sqlite3
import json
import time
from datetime import datetime, timezone

API_URL = "http://10.107.67.92:8080/maquinas"
DB_PATH = "monitoramento.db"


def criar_tabela():
    with sqlite3.connect(DB_PATH) as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS leituras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_api INTEGER,
                timestamp_api TEXT,
                maquina TEXT NOT NULL,
                temperatura REAL,
                vibracao REAL,
                pressao REAL,
                producao REAL,
                status TEXT,
                coletado_em TEXT NOT NULL,
                dados_json TEXT NOT NULL,
                UNIQUE (id_api, timestamp_api, maquina)
            )
        """)


def coletar_dados():
    """Consulta a API e salva cada leitura na tabela."""

    resposta = requests.get(API_URL, timeout=10)
    resposta.raise_for_status()

    resposta_api = resposta.json()
    dados = resposta_api["dados"]

    if not isinstance(dados, list):
        raise ValueError("A API não retornou uma lista de leituras.")

    coletado_em = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    inseridos = 0
    duplicados = 0

    with sqlite3.connect(DB_PATH) as conexao:
        for leitura in dados:
            if not isinstance(leitura, dict):
                continue

            maquina = leitura.get("maquina")

            if not maquina:
                print(f"Leitura ignorada: campo 'maquina' ausente.")
                continue

            cursor = conexao.execute("""
                INSERT OR IGNORE INTO leituras (
                    id_api,
                    timestamp_api,
                    maquina,
                    temperatura,
                    vibracao,
                    pressao,
                    producao,
                    status,
                    coletado_em,
                    dados_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                leitura.get("id"),
                leitura.get("timestamp"),
                maquina,
                leitura.get("temperatura"),
                leitura.get("vibracao"),
                leitura.get("pressao"),
                leitura.get("producao"),
                leitura.get("status"),
                coletado_em,
                json.dumps(leitura, ensure_ascii=False)
            ))

            if cursor.rowcount == 1:
                inseridos += 1
            else:
                duplicados += 1

    print(
        f"[{coletado_em}] "
        f"Inseridos: {inseridos} | "
        f"Duplicados ignorados: {duplicados}"
    )


def iniciar_coleta():
    criar_tabela()

    print("Coletor iniciado.")
    print(f"API: {API_URL}")
    print(f"Banco: {DB_PATH}")

    while True:
        try:
            coletar_dados()

        except requests.RequestException as erro:
            print(f"Erro ao consultar a API: {erro}")

        except (ValueError, TypeError, sqlite3.Error) as erro:
            print(f"Erro ao processar ou salvar os dados: {erro}")

        time.sleep(5)


if __name__ == "__main__":
    iniciar_coleta()
