import sqlite3

with sqlite3.connect("monitoramento.db") as conexao:
    cursor = conexao.execute("""
        SELECT id, data_hora, dados_json
        FROM leituras
        ORDER BY id DESC
        LIMIT 5
    """)

    for registro in cursor.fetchall():
        print(registro)