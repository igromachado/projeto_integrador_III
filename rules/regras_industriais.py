from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Regra:
    maquina: str
    parametro: str
    unidade: str
    classificacao: str
    descricao: str
    condicao: Any

# Limites didáticos definidos no documento do projeto.
REGRAS = [
    Regra("TORNO_CNC_01", "temperatura", "°C", "Atenção", "Acima de 62 até 67 °C", lambda v: 62 < v <= 67),
    Regra("TORNO_CNC_01", "temperatura", "°C", "Crítico", "Acima de 67 °C", lambda v: v > 67),
    Regra("TORNO_CNC_01", "vibracao", "mm/s", "Atenção", "Acima de 2,8 até 3,6 mm/s", lambda v: 2.8 < v <= 3.6),
    Regra("TORNO_CNC_01", "vibracao", "mm/s", "Crítico", "Acima de 3,6 mm/s", lambda v: v > 3.6),
    Regra("TORNO_CNC_01", "rotacao", "RPM", "Atenção", "Abaixo de 2.900 RPM", lambda v: v < 2900),
    Regra("TORNO_CNC_01", "rotacao", "RPM", "Crítico", "Abaixo de 2.750 RPM", lambda v: v < 2750),
    Regra("TORNO_CNC_01", "desgaste", "%", "Atenção", "Acima de 60%", lambda v: 60 < v <= 85),
    Regra("TORNO_CNC_01", "desgaste", "%", "Crítico", "Acima de 85%", lambda v: 85 < v <= 90),
    Regra("TORNO_CNC_01", "desgaste", "%", "Manutenção", "Acima de 90%", lambda v: v > 90),

    Regra("PRENSA_HIDRAULICA_01", "pressao", "bar", "Atenção", "Abaixo de 135 até 125 bar", lambda v: 125 <= v < 135),
    Regra("PRENSA_HIDRAULICA_01", "pressao", "bar", "Crítico", "Abaixo de 125 bar", lambda v: v < 125),
    Regra("PRENSA_HIDRAULICA_01", "temperatura", "°C", "Atenção", "Acima de 62 até 66 °C", lambda v: 62 < v <= 66),
    Regra("PRENSA_HIDRAULICA_01", "temperatura", "°C", "Crítico", "Acima de 66 °C", lambda v: v > 66),
    Regra("PRENSA_HIDRAULICA_01", "vibracao", "mm/s", "Atenção", "Acima de 2,5 até 3,3 mm/s", lambda v: 2.5 < v <= 3.3),
    Regra("PRENSA_HIDRAULICA_01", "vibracao", "mm/s", "Crítico", "Acima de 3,3 mm/s", lambda v: v > 3.3),

    Regra("ESTEIRA_01", "carga", "%", "Atenção", "Acima de 85% até 92%", lambda v: 85 < v <= 92),
    Regra("ESTEIRA_01", "carga", "%", "Crítico", "Acima de 92%", lambda v: v > 92),
    Regra("ESTEIRA_01", "velocidade", "m/s", "Atenção", "Abaixo de 1,7 m/s", lambda v: v < 1.7),
    Regra("ESTEIRA_01", "velocidade", "m/s", "Crítico", "Abaixo de 1,55 m/s", lambda v: v < 1.55),
    Regra("ESTEIRA_01", "temperatura", "°C", "Atenção", "Acima de 44 até 47 °C", lambda v: 44 < v <= 47),
    Regra("ESTEIRA_01", "temperatura", "°C", "Crítico", "Acima de 47 °C", lambda v: v > 47),
    Regra("ESTEIRA_01", "vibracao", "mm/s", "Atenção", "Acima de 3,0 até 3,6 mm/s", lambda v: 3.0 < v <= 3.6),
    Regra("ESTEIRA_01", "vibracao", "mm/s", "Crítico", "Acima de 3,6 mm/s", lambda v: v > 3.6),

    Regra("ROBO_SOLDAGEM_01", "temperatura", "°C", "Atenção", "Acima de 75 até 85 °C", lambda v: 75 < v <= 85),
    Regra("ROBO_SOLDAGEM_01", "temperatura", "°C", "Crítico", "Acima de 85 °C", lambda v: v > 85),
    Regra("ROBO_SOLDAGEM_01", "corrente", "A", "Atenção", "Abaixo de 16,5 A ou acima de 20 A", lambda v: v < 16.5 or v > 20),
    Regra("ROBO_SOLDAGEM_01", "falhas", "", "Atenção", "De 3 a 5 falhas acumuladas", lambda v: 3 <= v <= 5),
    Regra("ROBO_SOLDAGEM_01", "falhas", "", "Manutenção", "Acima de 5 falhas acumuladas", lambda v: v > 5),

    Regra("COMPRESSOR_01", "pressao", "bar", "Atenção", "Abaixo de 7,5 até 6,5 bar", lambda v: 6.5 <= v <= 7.5),
    Regra("COMPRESSOR_01", "pressao", "bar", "Crítico", "Abaixo de 6,5 bar", lambda v: v < 6.5),
    Regra("COMPRESSOR_01", "temperatura", "°C", "Atenção", "Acima de 75 até 85 °C", lambda v: 75 < v <= 85),
    Regra("COMPRESSOR_01", "temperatura", "°C", "Crítico", "Acima de 85 °C", lambda v: v > 85),
    Regra("COMPRESSOR_01", "vibracao", "mm/s", "Atenção", "Acima de 4,0 até 5,5 mm/s", lambda v: 4.0 < v <= 5.5),
    Regra("COMPRESSOR_01", "vibracao", "mm/s", "Manutenção", "Acima de 5,5 mm/s", lambda v: v > 5.5),
    Regra("COMPRESSOR_01", "desgaste", "%", "Atenção", "Acima de 60 até 85%", lambda v: 60 < v <= 85),
    Regra("COMPRESSOR_01", "desgaste", "%", "Crítico", "Acima de 85%", lambda v: v > 85),
    Regra("COMPRESSOR_01", "consumo", "kW", "Atenção", "Acima de 8,0 até 8,8 kW", lambda v: 8.0 < v <= 8.8),
    Regra("COMPRESSOR_01", "consumo", "kW", "Crítico", "Acima de 8,8 kW", lambda v: v > 8.8),

    Regra("EMBALADORA_01", "velocidade", "", "Atenção", "Abaixo de 25", lambda v: v < 25),
    Regra("EMBALADORA_01", "velocidade", "", "Atenção", "Acima de 35 até 38", lambda v: 35 < v <= 38),
    Regra("EMBALADORA_01", "velocidade", "", "Crítico", "Acima de 38", lambda v: v > 38),
    Regra("EMBALADORA_01", "temperatura", "°C", "Atenção", "Acima de 48 até 50 °C", lambda v: 48 < v <= 50),
    Regra("EMBALADORA_01", "temperatura", "°C", "Crítico", "Acima de 50 °C", lambda v: v > 50),
    Regra("EMBALADORA_01", "falhas", "", "Atenção", "De 3 a 4 falhas acumuladas", lambda v: 3 <= v <= 4),
    Regra("EMBALADORA_01", "falhas", "", "Manutenção", "5 ou mais falhas acumuladas", lambda v: v >= 5),
]

ALIASES = {
    "rotacao": ("rotacao", "rpm"),
    "carga": ("carga", "carga_percentual"),
    "velocidade": ("velocidade", "velocidade_linha"),
    "corrente": ("corrente", "corrente_eletrica"),
    "falhas": ("falhas", "falhas_acumuladas"),
    "consumo": ("consumo", "consumo_energetico", "potencia", "energia"),
}
# Faixas normais de operação por máquina e parâmetro.
# None representa ausência de limite naquele sentido.
# Os indicadores de inclusão definem se o extremo pertence à faixa normal.

FAIXAS_NORMAIS = {
    ("TORNO_CNC_01", "temperatura"): {
        "min": None, "max": 62,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("TORNO_CNC_01", "vibracao"): {
        "min": None, "max": 2.8,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("TORNO_CNC_01", "rotacao"): {
        "min": 2900, "max": None,
        "min_inclusivo": True, "max_inclusivo": False,
    },
    ("TORNO_CNC_01", "desgaste"): {
        "min": None, "max": 60,
        "min_inclusivo": False, "max_inclusivo": True,
    },

    ("PRENSA_HIDRAULICA_01", "pressao"): {
        "min": 135, "max": None,
        "min_inclusivo": True, "max_inclusivo": False,
    },
    ("PRENSA_HIDRAULICA_01", "temperatura"): {
        "min": None, "max": 62,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("PRENSA_HIDRAULICA_01", "vibracao"): {
        "min": None, "max": 2.5,
        "min_inclusivo": False, "max_inclusivo": True,
    },

    ("ESTEIRA_01", "carga"): {
        "min": None, "max": 85,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("ESTEIRA_01", "velocidade"): {
        "min": 1.7, "max": None,
        "min_inclusivo": True, "max_inclusivo": False,
    },
    ("ESTEIRA_01", "temperatura"): {
        "min": None, "max": 44,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("ESTEIRA_01", "vibracao"): {
        "min": None, "max": 3.0,
        "min_inclusivo": False, "max_inclusivo": True,
    },

    ("ROBO_SOLDAGEM_01", "temperatura"): {
        "min": None, "max": 75,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("ROBO_SOLDAGEM_01", "corrente"): {
        "min": 16.5, "max": 20,
        "min_inclusivo": True, "max_inclusivo": True,
    },
    ("ROBO_SOLDAGEM_01", "falhas"): {
        "min": None, "max": 2,
        "min_inclusivo": False, "max_inclusivo": True,
    },

    ("COMPRESSOR_01", "pressao"): {
        "min": 7.5, "max": None,
        "min_inclusivo": False, "max_inclusivo": False,
    },
    ("COMPRESSOR_01", "temperatura"): {
        "min": None, "max": 75,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("COMPRESSOR_01", "vibracao"): {
        "min": None, "max": 4.0,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("COMPRESSOR_01", "desgaste"): {
        "min": None, "max": 60,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("COMPRESSOR_01", "consumo"): {
        "min": None, "max": 8.0,
        "min_inclusivo": False, "max_inclusivo": True,
    },

    ("EMBALADORA_01", "velocidade"): {
        "min": 25, "max": 35,
        "min_inclusivo": True, "max_inclusivo": True,
    },
    ("EMBALADORA_01", "temperatura"): {
        "min": None, "max": 48,
        "min_inclusivo": False, "max_inclusivo": True,
    },
    ("EMBALADORA_01", "falhas"): {
        "min": None, "max": 2,
        "min_inclusivo": False, "max_inclusivo": True,
    },
}

PRIORIDADE = {"Normal": 0, "Atenção": 1, "Crítico": 2, "Manutenção": 3}

def avaliar_leitura(linha: dict) -> list[dict]:
    maquina = str(linha.get("maquina", ""))
    alertas = []
    for regra in REGRAS:
        if regra.maquina != maquina:
            continue
        chaves = ALIASES.get(regra.parametro, (regra.parametro,))
        valor = next((linha.get(chave) for chave in chaves if linha.get(chave) is not None), None)
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            continue
        if regra.condicao(valor):
            alertas.append({
                "maquina": maquina,
                "parametro": regra.parametro,
                "valor": valor,
                "unidade": regra.unidade,
                "classificacao": regra.classificacao,
                "limite": regra.descricao,
                "justificativa": f"{regra.parametro.capitalize()} = {valor:g} {regra.unidade}. Regra: {regra.descricao}.",
            })

    # Mantém apenas a classificação mais severa por parâmetro.
    consolidados = {}
    for alerta in alertas:
        chave = alerta["parametro"]
        atual = consolidados.get(chave)
        if atual is None or PRIORIDADE[alerta["classificacao"]] > PRIORIDADE[atual["classificacao"]]:
            consolidados[chave] = alerta
    return list(consolidados.values())

def avaliar_maquinas(ultimas: list[dict], agora=None) -> list[dict]:
    import pandas as pd
    from datetime import timezone
    agora = agora or pd.Timestamp.now(tz="UTC")
    resultado = []
    for linha in ultimas:
        maquina = linha.get("maquina")
        data = linha.get("data_hora")
        if pd.notna(data):
            data = pd.Timestamp(data)
            if data.tzinfo is None:
                data = data.tz_localize("UTC")
            if (agora - data).total_seconds() > 15:
                resultado.append({
                    "maquina": maquina, "parametro": "comunicacao",
                    "valor": None, "unidade": "", "classificacao": "Sem comunicação",
                    "limite": "Mais de 15 segundos sem nova leitura",
                    "justificativa": f"Última leitura recebida em {data.strftime('%d/%m/%Y %H:%M:%S UTC')}.",
                })
        status = str(linha.get("status", "")).upper()
        if status == "MANUTENCAO":
            resultado.append({
                "maquina": maquina, "parametro": "status", "valor": status,
                "unidade": "", "classificacao": "Manutenção", "limite": "Status recebido = MANUTENCAO",
                "justificativa": "A máquina informou status de manutenção.",
            })
        elif status == "PARADA":
            resultado.append({
                "maquina": maquina, "parametro": "status", "valor": status,
                "unidade": "", "classificacao": "Parada", "limite": "Status recebido = PARADA",
                "justificativa": "A máquina informou status de parada.",
            })
        resultado.extend(avaliar_leitura(linha))
    return resultado
