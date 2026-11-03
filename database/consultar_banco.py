import sqlite3

with sqlite3.connect("monitoramento.db") as conexao:
    cursor = conexao.execute("""
        SELECT
            id,
            id_api,
            timestamp_api,
            maquina,
            temperatura,
            vibracao,
            pressao,
            producao,
            status
        FROM leituras
        ORDER BY id DESC
        LIMIT 10
    """)

    registros = cursor.fetchall()

    for registro in registros:
        print(registro)

    print(f"\nTotal de registros: {len(registros)}")