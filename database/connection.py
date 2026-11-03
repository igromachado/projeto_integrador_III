import sqlite3
from pathlib import Path
from contextlib import contextmanager

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "monitoramento.db"


@contextmanager
def get_connection():
    conexao = sqlite3.connect(DB_PATH)

    try:
        yield conexao
        conexao.commit()

    except Exception:
        conexao.rollback()
        raise

    finally:
        conexao.close()