
import requests
import json
import time

from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database.connection import engine


API_URL = "http://10.222.107.92:8080/maquinas"
INTERVALO_COLETA = 5


def criar_tabela():
    """Cria a tabela caso ainda não exista."""

    query = text("""
        CREATE TABLE IF NOT EXISTS leituras (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            id_api BIGINT NOT NULL,
            timestamp_api VARCHAR(50) NOT NULL,
            maquina VARCHAR(100) NOT NULL,
            temperatura DOUBLE,
            vibracao DOUBLE,
            pressao DOUBLE,
            producao DOUBLE,
            status VARCHAR(50),
            coletado_em DATETIME NOT NULL,
            dados_json LONGTEXT NOT NULL,

            UNIQUE KEY uk_leitura (
                id_api,
                timestamp_api,
                maquina
            )
        )
    """)

    with engine.begin() as conexao:
        conexao.execute(query)


def coletar_dados():
    """Consulta a API e salva as leituras sem duplicar registros."""

    resposta = requests.get(API_URL, timeout=10)
    resposta.raise_for_status()

    resposta_api = resposta.json()
    dados = resposta_api.get("dados")

    if not isinstance(dados, list):
        raise ValueError(
            "A API não retornou uma lista válida de leituras."
        )

    coletado_em = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    inseridos = 0
    duplicados = 0
    ignorados = 0

    query = text("""
        INSERT IGNORE INTO leituras (
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
        VALUES (
            :id_api,
            :timestamp_api,
            :maquina,
            :temperatura,
            :vibracao,
            :pressao,
            :producao,
            :status,
            :coletado_em,
            :dados_json
        )
    """)

    with engine.begin() as conexao:

        for leitura in dados:

            if not isinstance(leitura, dict):
                ignorados += 1
                continue

            id_api = leitura.get("id")
            timestamp_api = leitura.get("timestamp")
            maquina = leitura.get("maquina")

            # Não permite inserir registros sem identificadores
            if (
                id_api is None
                or timestamp_api is None
                or not maquina
            ):
                ignorados += 1
                continue

            parametros = {
                "id_api": id_api,
                "timestamp_api": str(timestamp_api),
                "maquina": maquina,
                "temperatura": leitura.get("temperatura"),
                "vibracao": leitura.get("vibracao"),
                "pressao": leitura.get("pressao"),
                "producao": leitura.get("producao"),
                "status": leitura.get("status"),
                "coletado_em": coletado_em,
                "dados_json": json.dumps(
                    leitura,
                    ensure_ascii=False,
                ),
            }

            resultado = conexao.execute(
                query,
                parametros,
            )

            if resultado.rowcount == 1:
                inseridos += 1
            else:
                duplicados += 1

    print(
        f"[{coletado_em}] "
        f"Inseridos: {inseridos} | "
        f"Duplicados ignorados: {duplicados} | "
        f"Registros inválidos: {ignorados}"
    )


def iniciar_coleta():

    try:
        criar_tabela()
        print("Tabela verificada/criada com sucesso.")

    except SQLAlchemyError as erro:
        print(f"Erro ao preparar o banco: {erro}")
        return

    print("Coletor iniciado.")
    print(f"API: {API_URL}")
    print("Banco: MySQL - Clever Cloud")
    print(f"Intervalo: {INTERVALO_COLETA} segundos")

    while True:

        try:
            coletar_dados()

        except requests.RequestException as erro:
            print(f"Erro ao consultar a API: {erro}")

        except (ValueError, TypeError, KeyError) as erro:
            print(f"Erro ao processar os dados: {erro}")

        except SQLAlchemyError as erro:
            print(f"Erro ao salvar os dados: {erro}")

        except Exception as erro:
            print(f"Erro inesperado: {erro}")

        time.sleep(INTERVALO_COLETA)


if __name__ == "__main__":
    iniciar_coleta()
