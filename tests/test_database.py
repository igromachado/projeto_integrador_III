
import sqlite3

conexao = sqlite3.connect("monitoramento.db")

cursor = conexao.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")

tabelas = cursor.fetchall()

print("Tabelas encontradas:")

for tabela in tabelas:
    print(tabela[0])

conexao.close()
