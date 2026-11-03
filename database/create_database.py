
import sqlite3

DB_PATH = "monitoramento.db"


def criar_banco():
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

    print("Tabela leituras criada/verificada com sucesso.")


if __name__ == "__main__":
    criar_banco()

