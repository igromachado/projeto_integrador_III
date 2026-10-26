
import requests
import json

API_URL = "http://10.107.67.92:8080/maquinas"

try:
    resposta = requests.get(API_URL, timeout=10)

    print("Status HTTP:", resposta.status_code)
    print("Content-Type:", resposta.headers.get("Content-Type"))
    print("Resposta recebida:")

    try:
        dados = resposta.json()
        print(json.dumps(dados, indent=4, ensure_ascii=False))
        print("\nTipo de dado:", type(dados).__name__)

    except ValueError:
        print(resposta.text)

except requests.RequestException as erro:
    print("Erro de conexão:", erro)
