from __future__ import annotations
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from rules.regras_industriais import avaliar_maquinas
from sqlalchemy import inspect, text
from database.connection import engine


# A conexão é feita com o MySQL remoto da Clever Cloud pelo engine.
st.set_page_config(
    page_title="Monitoramento Industrial",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_data(ttl=5, show_spinner=False)
def carregar_dados(ultima_atualizacao: int) -> pd.DataFrame:
    """Carrega as leituras do MySQL e recupera métricas extras do JSON."""
    del ultima_atualizacao  # usado como chave para invalidar o cache manualmente

    with engine.connect() as conexao:
        if not inspect(engine).has_table("leituras"):
            return pd.DataFrame()

        df = pd.read_sql_query(
            text("""
                SELECT
                    id,
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
                FROM leituras
                ORDER BY timestamp_api
            """),
            conexao,
        )

    if df.empty:
        return df

    # Campos disponíveis na API, mas ainda não armazenados em colunas próprias.
    def extrair_json(valor: object, chave: str) -> object:
        try:
            objeto = json.loads(valor) if isinstance(valor, str) else {}
            return objeto.get(chave)
        except (json.JSONDecodeError, TypeError):
            return None

    campos_extras = (
        "tipo", "ciclos", "defeitos", "desgaste", "rotacao", "rpm",
        "carga", "carga_percentual", "velocidade", "velocidade_linha",
        "corrente", "corrente_eletrica", "falhas", "falhas_acumuladas",
        "consumo", "consumo_energetico", "potencia", "energia",
        "rejeitados", "paradas", "horas_operacao",
    )
    for campo in campos_extras:
        if campo not in df.columns:
            df[campo] = df["dados_json"].apply(
                lambda valor, nome=campo: extrair_json(valor, nome)
            )

    df["data_hora"] = pd.to_datetime(
        df["timestamp_api"], errors="coerce", utc=True
    )
    df["coletado_em"] = pd.to_datetime(
        df["coletado_em"], errors="coerce", utc=True
    )

    colunas_numericas = [
        "temperatura", "vibracao", "pressao", "producao",
        "ciclos", "defeitos", "desgaste", "rotacao", "rpm", "carga",
        "carga_percentual", "velocidade", "velocidade_linha", "corrente",
        "corrente_eletrica", "falhas", "falhas_acumuladas", "consumo",
        "consumo_energetico", "potencia", "energia", "rejeitados",
        "paradas", "horas_operacao",
    ]
    for coluna in colunas_numericas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df["maquina"] = df["maquina"].fillna("Máquina não identificada")
    df["status"] = df["status"].fillna("SEM STATUS").astype(str).str.upper()
    return df


def formatar_numero(valor: float | int | None, casas: int = 0) -> str:

    if valor is None or pd.isna(valor):

        return "—"

    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Cabeçalho

st.title("🏭 Monitoramento Industrial")

st.caption("Acompanhamento de produção e condições operacionais das máquinas")


# Controle simples de atualização

if "versao_cache" not in st.session_state:

    st.session_state.versao_cache = 0


with st.sidebar:

    st.header("Filtros")

    if st.button("🔄 Atualizar dados", use_container_width=True):

        st.session_state.versao_cache += 1

        st.rerun()

    st.caption("Os dados são consultados diretamente no MySQL da Clever Cloud. Atualização automática do cache a cada 5 segundos.")


df = carregar_dados(st.session_state.versao_cache)


if df.empty:

    st.warning("Ainda não há leituras no banco de dados ou a tabela 'leituras' não foi encontrada.")

    st.info("Mantenha o coletor.py em execução e confirme se ele está gravando na tabela leituras do MySQL.")

    st.stop()


# Filtros

maquinas_disponiveis = sorted(df["maquina"].dropna().unique().tolist())

status_disponiveis = sorted(df["status"].dropna().unique().tolist())


with st.sidebar:

    maquinas_selecionadas = st.multiselect(

        "Máquinas", maquinas_disponiveis, default=maquinas_disponiveis

    )

    status_selecionados = st.multiselect(

        "Status", status_disponiveis, default=status_disponiveis

    )


    datas_validas = df["data_hora"].dropna()

    if not datas_validas.empty:

        data_min = datas_validas.min().date()

        data_max = datas_validas.max().date()

        periodo = st.date_input(

            "Período das leituras",

            value=(data_min, data_max),

            min_value=data_min,

            max_value=data_max,

        )

    else:

        periodo = None


filtrado = df[

    df["maquina"].isin(maquinas_selecionadas)

    & df["status"].isin(status_selecionados)

].copy()


if periodo and isinstance(periodo, (tuple, list)) and len(periodo) == 2:

    inicio = pd.Timestamp(periodo[0], tz="UTC")

    fim = pd.Timestamp(periodo[1], tz="UTC") + pd.Timedelta(days=1)

    filtrado = filtrado[

        filtrado["data_hora"].ge(inicio) & filtrado["data_hora"].lt(fim)

    ]


if filtrado.empty:

    st.warning("Nenhuma leitura encontrada para os filtros selecionados.")

    st.stop()


# Última leitura de cada máquina dentro do período/filtros.

ultimas = (

    filtrado.dropna(subset=["data_hora"])

    .sort_values("data_hora")

    .groupby("maquina", as_index=False)

    .tail(1)

)


# Avaliação das regras industriais usando a leitura mais recente de cada máquina.

# A avaliação usa o conjunto completo, independentemente do filtro de período do histórico.

ultimas_gerais = (

    df.dropna(subset=["data_hora"])

    .sort_values("data_hora")

    .groupby("maquina", as_index=False)

    .tail(1)

)

registros_atuais = ultimas_gerais.to_dict(orient="records")

alertas_atuais = avaliar_maquinas(registros_atuais)

alertas_atuais = [

    alerta for alerta in alertas_atuais

    if alerta["maquina"] in maquinas_selecionadas

]


# Diagnóstico combinado: dois ou mais indicadores da mesma máquina em condição anormal.

for maquina in sorted({a["maquina"] for a in alertas_atuais}):

    indicadores_alerta = {

        a["parametro"] for a in alertas_atuais

        if a["maquina"] == maquina

        and a["classificacao"] in ("Atenção", "Crítico", "Manutenção")

    }

    if len(indicadores_alerta) >= 2:

        alertas_atuais.append({

            "maquina": maquina,

            "parametro": "diagnostico",

            "valor": None,

            "unidade": "",

            "classificacao": "Diagnóstico combinado",

            "limite": "Dois ou mais indicadores simultaneamente fora da faixa normal",

            "justificativa": "Indicadores afetados: " + ", ".join(sorted(indicadores_alerta)) + ".",

        })


# Indicadores gerais

quantidade_maquinas = filtrado["maquina"].nunique()

quantidade_leituras = len(filtrado)

maquinas_atencao = len({

    alerta["maquina"] for alerta in alertas_atuais

    if alerta["classificacao"] in (

        "Atenção", "Crítico", "Manutenção", "Sem comunicação", "Parada"

    )

})

producao_atual = ultimas["producao"].sum(min_count=1)


st.subheader("Visão geral")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Máquinas monitoradas", formatar_numero(quantidade_maquinas))

c2.metric("Leituras no período", formatar_numero(quantidade_leituras))

c3.metric("Máquinas em atenção", formatar_numero(maquinas_atencao))

c4.metric("Produção registrada", formatar_numero(producao_atual))


st.divider()


# Painel de alertas operacionais

st.subheader("🚨 Alertas e condições operacionais")

if alertas_atuais:

    ordem = {"Sem comunicação": 0, "Manutenção": 1, "Crítico": 2, "Parada": 3,

             "Atenção": 4, "Diagnóstico combinado": 5}

    alertas_ordenados = sorted(

        alertas_atuais,

        key=lambda a: (ordem.get(a["classificacao"], 9), a["maquina"], a["parametro"]),

    )

    tabela_alertas = pd.DataFrame(alertas_ordenados).rename(columns={

        "maquina": "Máquina",

        "parametro": "Indicador",

        "valor": "Valor observado",

        "unidade": "Unidade",

        "classificacao": "Classificação",

        "limite": "Regra / limite aplicado",

        "justificativa": "Justificativa",

    })

    st.dataframe(tabela_alertas, use_container_width=True, hide_index=True)

    st.caption("Os alertas são recalculados a partir da leitura mais recente de cada máquina. Leituras ausentes não são tratadas como zero.")

else:

    st.success("Nenhuma regra de alerta foi acionada nas leituras mais recentes das máquinas selecionadas.")


st.divider()


# Gráficos temporais

st.subheader("Evolução dos indicadores")

col_esq, col_dir = st.columns(2)


with col_esq:

    metricas_temperatura = filtrado.dropna(subset=["temperatura", "data_hora"])

    if not metricas_temperatura.empty:

        fig_temp = px.line(

            metricas_temperatura,

            x="data_hora",

            y="temperatura",

            color="maquina",

            markers=True,

            title="Temperatura por máquina",

            labels={"data_hora": "Data/hora", "temperatura": "Temperatura (°C)", "maquina": "Máquina"},

        )

        fig_temp.update_layout(legend_title_text="Máquina", margin=dict(l=10, r=10, t=50, b=10))

        st.plotly_chart(fig_temp, use_container_width=True)

    else:

        st.info("Não há dados de temperatura no período selecionado.")


with col_dir:

    metricas_vibracao = filtrado.dropna(subset=["vibracao", "data_hora"])

    if not metricas_vibracao.empty:

        fig_vib = px.line(

            metricas_vibracao,

            x="data_hora",

            y="vibracao",

            color="maquina",

            markers=True,

            title="Vibração por máquina",

            labels={"data_hora": "Data/hora", "vibracao": "Vibração", "maquina": "Máquina"},

        )

        fig_vib.update_layout(legend_title_text="Máquina", margin=dict(l=10, r=10, t=50, b=10))

        st.plotly_chart(fig_vib, use_container_width=True)

    else:

        st.info("Não há dados de vibração no período selecionado.")


col_esq, col_dir = st.columns(2)

with col_esq:

    producao_df = filtrado.dropna(subset=["producao", "data_hora"])

    if not producao_df.empty:

        fig_prod = px.line(

            producao_df,

            x="data_hora",

            y="producao",

            color="maquina",

            markers=True,

            title="Produção registrada ao longo do tempo",

            labels={"data_hora": "Data/hora", "producao": "Produção", "maquina": "Máquina"}

        )

        fig_prod.update_layout(legend_title_text="Máquina", margin=dict(l=10, r=10, t=50, b=10))

        st.plotly_chart(fig_prod, use_container_width=True)

    else:

        st.info("Não há dados de produção no período selecionado.")


with col_dir:

    status_df = ultimas.groupby("status", as_index=False).size().rename(columns={"size": "maquinas"})

    fig_status = px.pie(

        status_df,

        names="status",

        values="maquinas",

        hole=0.55,

        title="Distribuição do status atual",

    )

    fig_status.update_layout(margin=dict(l=10, r=10, t=50, b=10))

    st.plotly_chart(fig_status, use_container_width=True)


# Tabela de situação atual

st.divider()

st.subheader("Situação atual por máquina")

colunas_status = [

    "maquina", "tipo", "status", "temperatura", "vibracao", "pressao",

    "producao", "ciclos", "defeitos", "desgaste", "data_hora",

]

colunas_status = [coluna for coluna in colunas_status if coluna in ultimas.columns]

tabela_status = ultimas[colunas_status].sort_values("maquina", na_position="last").copy()

tabela_status = tabela_status.rename(columns={

    "maquina": "Máquina",

    "tipo": "Tipo",

    "status": "Status",

    "temperatura": "Temperatura (°C)",

    "vibracao": "Vibração",

    "pressao": "Pressão",

    "producao": "Produção",

    "ciclos": "Ciclos",

    "defeitos": "Defeitos",

    "desgaste": "Desgaste",

    "data_hora": "Data/hora da leitura",

})

st.dataframe(tabela_status, use_container_width=True, hide_index=True)


# Análise de defeitos e desgaste quando a API fornecer esses campos.

col_esq, col_dir = st.columns(2)

with col_esq:

    defeitos_df = ultimas.dropna(subset=["defeitos"])

    if not defeitos_df.empty:

        fig_def = px.bar(

            defeitos_df.sort_values("defeitos", ascending=False),

            x="maquina", y="defeitos", title="Defeitos na última leitura por máquina",

            labels={"maquina": "Máquina", "defeitos": "Defeitos"},

        )

        st.plotly_chart(fig_def, use_container_width=True)


with col_dir:

    desgaste_df = ultimas.dropna(subset=["desgaste"])

    if not desgaste_df.empty:

        fig_desg = px.bar(

            desgaste_df.sort_values("desgaste", ascending=False),

            x="maquina", y="desgaste", title="Desgaste na última leitura por máquina",

            labels={"maquina": "Máquina", "desgaste": "Desgaste"},

        )

        st.plotly_chart(fig_desg, use_container_width=True)


# Histórico detalhado e exportação

with st.expander("Consultar histórico detalhado"):

    historico = filtrado.sort_values("data_hora", ascending=False).copy()

    historico["data_hora"] = historico["data_hora"].dt.strftime("%d/%m/%Y %H:%M:%S UTC")

    colunas_historico = [

        "id", "id_api", "data_hora", "maquina", "tipo", "temperatura",

        "vibracao", "pressao", "producao", "ciclos", "defeitos", "desgaste", "status",

    ]

    colunas_historico = [c for c in colunas_historico if c in historico.columns]

    st.dataframe(historico[colunas_historico], use_container_width=True, hide_index=True)


    csv = historico[colunas_historico].to_csv(index=False).encode("utf-8-sig")

    st.download_button(

        "⬇️ Exportar histórico em CSV",

        data=csv,

        file_name="historico_monitoramento.csv",

        mime="text/csv",

    )


st.caption(f"Banco de dados: MySQL - Clever Cloud · Última atualização da página: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M:%S')}")
