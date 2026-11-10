from __future__ import annotations

import json
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import inspect, text

from database.connection import engine
from rules.regras_industriais import avaliar_maquinas

# A conexão é feita com o MySQL remoto da Clever Cloud pelo engine.
st.set_page_config(
    page_title="Monitoramento Industrial",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Identidade visual: sala de controle, tema escuro, cantos retos
# ---------------------------------------------------------------------------
PALETA = ["#3FA7C9", "#F5A524", "#3DB87A", "#9A8CE8", "#E5688A", "#8796A3"]

# classificação -> (cor do texto, cor de fundo)
TONS = {
    "Sem comunicação": ("#B4C0CA", "rgba(135,150,163,.18)"),
    "Manutenção": ("#FFB067", "rgba(255,150,50,.16)"),
    "Crítico": ("#FF7B80", "rgba(229,72,77,.18)"),
    "Parada": ("#F5C451", "rgba(245,165,36,.16)"),
    "Atenção": ("#F5C451", "rgba(245,165,36,.16)"),
    "Diagnóstico combinado": ("#FF9AA0", "rgba(229,72,77,.26)"),
}

ORDEM_GRAVIDADE = {
    "Sem comunicação": 0, "Manutenção": 1, "Crítico": 2,
    "Diagnóstico combinado": 3, "Parada": 4, "Atenção": 5,
}

# Classificações exibidas na tela de alertas críticos (ajuste se precisar).
CLASSIFICACOES_CRITICAS = ("Sem comunicação", "Manutenção", "Crítico", "Diagnóstico combinado")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp button, .stApp input, .stApp textarea { font-family: 'IBM Plex Sans', sans-serif; }

.stApp { background: #0E1318; color: #E6EBEF; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1500px; }

/* Sidebar */
[data-testid="stSidebar"] { background: #0A0E12; border-right: 1px solid #222C35; }
.marca { margin: .2rem 0 1.1rem 0; padding-left: .7rem; border-left: 3px solid #3FA7C9; }
.marca-nome { font-weight: 700; font-size: 1rem; line-height: 1.15; color: #E6EBEF; letter-spacing: .01em; }
.marca-sub { font-size: .76rem; color: #8796A3; margin-top: .1rem; }

/* Controles com cantos retos */
.stButton button, .stDownloadButton button { border-radius: 3px; font-weight: 600; }
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"] { border-radius: 3px; }
[data-baseweb="tag"] { border-radius: 2px; }
[data-testid="stExpander"] { border-radius: 3px; }

/* Barra de título da página */
.topo { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; flex-wrap: wrap;
        padding-bottom: 1rem; margin-bottom: 1.3rem; border-bottom: 1px solid #26323D; }
.topo.alerta { border-bottom: 2px solid #E5484D; }
.topo h1 { color: #FFFFFF; font-size: 1.6rem; font-weight: 600; margin: 0; padding: 0; letter-spacing: -.01em; }
.topo p { color: #8796A3; margin: .3rem 0 0 0; font-size: .9rem; }
.chip { display: inline-flex; align-items: center; gap: .5rem; border-radius: 2px;
        padding: .38rem .8rem; font-size: .82rem; font-weight: 600; border: 1px solid; }
.chip i { width: 8px; height: 8px; display: inline-block; background: currentColor; }
.chip-ok { color: #5FD39A; border-color: #1F5F43; background: rgba(61,184,122,.10); }
.chip-warn { color: #F5C451; border-color: #6B4C0F; background: rgba(245,165,36,.10); }
.chip-crit { color: #FF7B80; border-color: #7A2427; background: rgba(229,72,77,.12); }

/* Títulos de seção */
.secao { font-size: .95rem; font-weight: 600; color: #C9D3DB; margin: 1.7rem 0 .8rem 0;
         padding-bottom: .45rem; border-bottom: 1px solid #26323D; }

/* Indicadores */
.kpi { background: #151C23; border: 1px solid #26323D; border-radius: 3px; padding: 1rem 1.2rem;
       border-top: 3px solid #3FA7C9; height: 100%; }
.kpi-crit { border-top-color: #E5484D; }
.kpi-warn { border-top-color: #F5A524; }
.kpi-ok { border-top-color: #3DB87A; }
.kpi-rot { font-size: .8rem; color: #8796A3; font-weight: 500; }
.kpi-val { font-size: 2.1rem; font-weight: 600; color: #FFFFFF; line-height: 1.15; margin-top: .2rem;
           font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.kpi-det { font-size: .76rem; color: #6F7E8B; margin-top: .15rem; min-height: 1em; }

/* Gráficos e blocos */
[data-testid="stVerticalBlockBorderWrapper"] { background: #151C23; border-color: #26323D; border-radius: 3px; }

/* Grade de máquinas */
.grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
.tile { background: #151C23; border: 1px solid #26323D; border-left: 4px solid #3DB87A;
        border-radius: 3px; padding: .8rem .95rem; }
.tile-warn { border-left-color: #F5A524; }
.tile-crit { border-left-color: #E5484D; background: #1A1519; }
.tile-topo { display: flex; justify-content: space-between; align-items: center; gap: .5rem; }
.tile-nome { font-weight: 600; color: #FFFFFF; font-size: .95rem; }
.tile-estado { font-size: .72rem; font-weight: 600; }
.tile-ok .tile-estado { color: #5FD39A; }
.tile-warn .tile-estado { color: #F5C451; }
.tile-crit .tile-estado { color: #FF7B80; }
.tile-sub { font-size: .76rem; color: #8796A3; margin-top: .1rem; }
.tile-met { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin-top: .75rem;
            padding-top: .65rem; border-top: 1px solid #222C35; }
.tile-met b { display: block; font-size: 1.05rem; font-weight: 600; color: #E6EBEF;
              font-variant-numeric: tabular-nums; }
.tile-met span { font-size: .68rem; color: #6F7E8B; }

/* Máquina em alerta crítico */
.maq { background: #151C23; border: 1px solid #26323D; border-left: 4px solid #E5484D;
       border-radius: 3px; padding: 1.05rem 1.25rem; margin-bottom: 12px; }
.maq-topo { display: flex; justify-content: space-between; align-items: flex-start; gap: .8rem; }
.maq-nome { font-size: 1.08rem; font-weight: 600; color: #FFFFFF; }
.maq-meta { font-size: .78rem; color: #8796A3; margin-top: .1rem; }
.maq-status { font-size: .74rem; font-weight: 600; background: #222C35; color: #C9D3DB;
              border-radius: 2px; padding: .2rem .55rem; white-space: nowrap; }
.alerta-linha { border-top: 1px solid #222C35; margin-top: .8rem; padding-top: .75rem; }
.alerta-cab { display: flex; justify-content: space-between; align-items: center; gap: .6rem; flex-wrap: wrap; }
.alerta-ind { font-weight: 600; color: #E6EBEF; text-transform: capitalize; }
.alerta-val { font-weight: 600; font-variant-numeric: tabular-nums; color: #FF7B80; margin-left: .35rem; }
.pill { font-size: .72rem; font-weight: 600; border-radius: 2px; padding: .15rem .5rem; }
.alerta-regra { font-size: .8rem; color: #8796A3; margin-top: .3rem; }
.alerta-just { font-size: .83rem; color: #C9D3DB; margin-top: .2rem; }

/* Estado vazio */
.vazio { background: #151C23; border: 1px solid #1F5F43; border-left: 4px solid #3DB87A;
         border-radius: 3px; padding: 1.6rem 1.5rem; }
.vazio b { font-size: 1.05rem; color: #5FD39A; }
.vazio p { color: #8796A3; margin: .35rem 0 0 0; }

.rodape { color: #6F7E8B; font-size: .76rem; margin-top: 2.2rem; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120, show_spinner=False)
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

    df["data_hora"] = pd.to_datetime(df["timestamp_api"], errors="coerce", utc=True)
    df["coletado_em"] = pd.to_datetime(df["coletado_em"], errors="coerce", utc=True)

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


def ultimas_leituras(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.dropna(subset=["data_hora"])
        .sort_values("data_hora")
        .groupby("maquina", as_index=False)
        .tail(1)
    )


def calcular_alertas(df: pd.DataFrame) -> list[dict]:
    """Avalia as regras na leitura mais recente de cada máquina (conjunto completo)."""
    alertas = avaliar_maquinas(ultimas_leituras(df).to_dict(orient="records"))

    # Diagnóstico combinado: dois ou mais indicadores da mesma máquina em condição anormal.
    for maquina in sorted({a["maquina"] for a in alertas}):
        indicadores = {
            a["parametro"] for a in alertas
            if a["maquina"] == maquina
            and a["classificacao"] in ("Atenção", "Crítico", "Manutenção")
        }
        if len(indicadores) >= 2:
            alertas.append({
                "maquina": maquina,
                "parametro": "diagnostico",
                "valor": None,
                "unidade": "",
                "classificacao": "Diagnóstico combinado",
                "limite": "Dois ou mais indicadores simultaneamente fora da faixa normal",
                "justificativa": "Indicadores afetados: " + ", ".join(sorted(indicadores)) + ".",
            })
    return alertas


# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------
def formatar_numero(valor: float | int | None, casas: int = 0) -> str:
    if valor is None or pd.isna(valor):
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tempo_desde(momento: pd.Timestamp | None) -> str:
    if momento is None or pd.isna(momento):
        return "horário desconhecido"
    minutos = int((pd.Timestamp.now(tz="UTC") - momento).total_seconds() // 60)
    if minutos < 1:
        return "agora há pouco"
    if minutos < 60:
        return f"há {minutos} min"
    if minutos < 1440:
        return f"há {minutos // 60} h"
    return f"há {minutos // 1440} d"


def cabecalho(titulo: str, subtitulo: str, chip: str, tom_chip: str, critico: bool = False) -> None:
    classe = "topo alerta" if critico else "topo"
    st.markdown(
        f'<div class="{classe}"><div><h1>{escape(titulo)}</h1><p>{escape(subtitulo)}</p></div>'
        f'<span class="chip chip-{tom_chip}"><i></i>{escape(chip)}</span></div>',
        unsafe_allow_html=True,
    )


def secao(titulo: str) -> None:
    st.markdown(f'<div class="secao">{escape(titulo)}</div>', unsafe_allow_html=True)


def kpi(rotulo: str, valor: str, detalhe: str = "", tom: str = "neutro") -> str:
    return (
        f'<div class="kpi kpi-{tom}"><div class="kpi-rot">{escape(rotulo)}</div>'
        f'<div class="kpi-val">{escape(valor)}</div><div class="kpi-det">{escape(detalhe)}</div></div>'
    )


def estilizar(fig, altura: int = 340, linhas: bool = True):
    fig.update_layout(
        template="plotly_dark",
        height=altura,
        colorway=PALETA,
        font=dict(family="IBM Plex Sans, sans-serif", color="#C9D3DB", size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=52, b=10),
        title=dict(font=dict(size=14, color="#E6EBEF"), x=0),
        legend=dict(orientation="h", y=-0.22, title_text=""),
        hovermode="x unified" if linhas else "closest",
    )
    fig.update_xaxes(gridcolor="#222C35", linecolor="#26323D", title_text=None)
    fig.update_yaxes(gridcolor="#222C35", linecolor="#26323D")
    return fig


# Intervalo sem leituras a partir do qual consideramos que houve uma lacuna.
LIMITE_LACUNA = pd.Timedelta(minutes=30)


def inserir_quebras(dados: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Insere um ponto vazio em cada lacuna, para a linha não ligar leituras distantes no tempo."""
    dados = dados[["data_hora", "maquina", coluna]].copy()
    dados["data_hora"] = dados["data_hora"].dt.tz_convert(None)  # UTC sem fuso
    partes = []
    for _, grupo in dados.sort_values("data_hora").groupby("maquina", sort=False):
        anterior = grupo["data_hora"].shift(1)
        pausa = (grupo["data_hora"] - anterior) > LIMITE_LACUNA
        quebras = grupo.loc[pausa].copy()
        quebras["data_hora"] = anterior[pausa] + pd.Timedelta(seconds=1)
        quebras[coluna] = float("nan")
        partes.append(pd.concat([grupo, quebras]))
    return pd.concat(partes).sort_values(["maquina", "data_hora"]).reset_index(drop=True)


def eixo_comprimido(datas: pd.Series):
    """Cria um eixo contínuo em que cada lacuna vira uma faixa estreita.

    Devolve: função data -> posição, função posição -> data, lista de lacunas,
    largura visual de cada lacuna e posição final do eixo.
    """
    t = datas.dropna().drop_duplicates().sort_values().reset_index(drop=True)
    origem = t.iloc[0]
    passos = t.diff()
    lacunas = [(t[i - 1], t[i]) for i in t.index[passos > LIMITE_LACUNA]]
    ativo = passos[passos <= LIMITE_LACUNA].sum().total_seconds()
    visual = max(ativo * 0.02, 1.0)

    def x_de(serie: pd.Series) -> pd.Series:
        x = (serie - origem).dt.total_seconds()
        for ini, fim in lacunas:
            x = x - (serie >= fim) * ((fim - ini).total_seconds() - visual)
        return x

    def x_escalar(momento: pd.Timestamp) -> float:
        return float(x_de(pd.Series([momento])).iloc[0])

    def real_de(posicao: float) -> pd.Timestamp:
        extra = sum(
            (fim - ini).total_seconds() - visual
            for ini, fim in lacunas if posicao >= x_escalar(fim)
        )
        return origem + pd.Timedelta(seconds=posicao + extra)

    return x_escalar, x_de, real_de, lacunas, visual, x_escalar(t.iloc[-1])


def grafico_temporal(dados: pd.DataFrame, coluna: str, titulo: str, rotulo: str,
                     altura: int = 340, cor: str | None = None):
    """Gráfico de linhas por máquina, sem espaços vazios entre períodos de leitura."""
    serie = inserir_quebras(dados, coluna)
    rotulos = {"data_hora": "Data/hora", "x": "Data/hora", coluna: rotulo, "maquina": "Máquina"}

    def grafico_eixo_real():
        fig = px.line(serie, x="data_hora", y=coluna, color="maquina",
                      title=titulo, labels=rotulos)
        fig.update_traces(connectgaps=False)
        if cor:
            fig.update_traces(line_color=cor, marker_color=cor, mode='markers')
        return estilizar(fig, altura)

    if not st.session_state.get("ocultar_lacunas", True):
        return grafico_eixo_real()

    try:
        reais = dados["data_hora"].dt.tz_convert(None)
        x_escalar, x_de, real_de, lacunas, visual, x_max = eixo_comprimido(reais)
        serie = serie.copy()
        serie["x"] = x_de(serie["data_hora"]).astype(float)
        serie["hora_real"] = serie["data_hora"].dt.strftime("%d/%m/%Y %H:%M:%S")
        if serie["x"].isna().all():
            raise ValueError("não foi possível calcular as posições do eixo")

        fig = px.line(serie, x="x", y=coluna, color="maquina", title=titulo,
                      labels=rotulos, custom_data=["hora_real"])
        fig.update_traces(
            connectgaps=False,
            hovertemplate="%{customdata[0]}<br>%{y:.2f}<extra>%{fullData.name}</extra>",
        )
        if cor:
            fig.update_traces(line_color=cor, marker_color=cor)
        estilizar(fig, altura, linhas=False)

        # Faixa sombreada marca onde houve interrupção das leituras.
        zonas = []
        for ini, fim in lacunas:
            inicio_faixa = x_escalar(ini)
            zonas.append((inicio_faixa, inicio_faixa + visual))
            fig.add_shape(type="rect", xref="x", yref="paper", x0=inicio_faixa,
                          x1=inicio_faixa + visual, y0=0, y1=1, fillcolor="#2E3B47",
                          opacity=0.7, line_width=0, layer="below")

        # Rótulos do eixo mostram a data e a hora reais de cada ponto.
        posicoes = [x_max * k / 5 for k in range(6)] if x_max > 0 else [0.0]
        posicoes = [float(p) for p in posicoes if not any(a < p < b for a, b in zonas)]
        margem = max(x_max * 0.01, 1.0)
        fig.update_xaxes(
            type="linear", range=[-margem, x_max + margem],
            tickmode="array", tickvals=posicoes,
            ticktext=[real_de(p).strftime("%d/%m %H:%M") for p in posicoes],
        )
        return fig
    except Exception as erro:  # rede de segurança: nunca deixar o gráfico em branco
        st.caption(f"Eixo sem lacunas indisponível ({type(erro).__name__}: {erro}). "
                   "Exibindo o eixo de tempo real.")
        return grafico_eixo_real()


def pill(classificacao: str) -> str:
    cor, fundo = TONS.get(classificacao, ("#B4C0CA", "rgba(135,150,163,.18)"))
    return f'<span class="pill" style="color:{cor};background:{fundo}">{escape(classificacao)}</span>'


def cartao_maquina(maquina: str, alertas: list[dict], status: str, momento) -> str:
    linhas = []
    for a in alertas:
        valor = ""
        if a.get("valor") is not None and not pd.isna(a["valor"]):
            valor = f'{formatar_numero(a["valor"], 2)} {escape(str(a.get("unidade") or ""))}'.strip()
        linhas.append(
            '<div class="alerta-linha"><div class="alerta-cab">'
            f'<span class="alerta-ind">{escape(str(a["parametro"]).replace("_", " "))}</span>'
            f'<span>{pill(a["classificacao"])}<span class="alerta-val">{valor}</span></span></div>'
            f'<div class="alerta-regra">Regra: {escape(str(a.get("limite") or "—"))}</div>'
            f'<div class="alerta-just">{escape(str(a.get("justificativa") or ""))}</div></div>'
        )
    return (
        '<div class="maq"><div class="maq-topo"><div>'
        f'<div class="maq-nome">{escape(maquina)}</div>'
        f'<div class="maq-meta">Última leitura {escape(tempo_desde(momento))}</div></div>'
        f'<span class="maq-status">{escape(status)}</span></div>' + "".join(linhas) + "</div>"
    )


def grade_maquinas(ultimas: pd.DataFrame, alertas: list[dict]) -> str:
    classes_por_maquina: dict[str, list[str]] = {}
    for a in alertas:
        classes_por_maquina.setdefault(a["maquina"], []).append(a["classificacao"])

    tiles = []
    for _, linha in ultimas.sort_values("maquina").iterrows():
        classes = classes_por_maquina.get(linha["maquina"], [])
        if any(c in CLASSIFICACOES_CRITICAS for c in classes):
            estado, rotulo = "crit", "Crítico"
        elif classes:
            estado, rotulo = "warn", "Atenção"
        else:
            estado, rotulo = "ok", "Normal"

        tipo = linha.get("tipo")
        subtitulo = f'{escape(str(tipo))}  ·  ' if isinstance(tipo, str) and tipo else ""
        subtitulo += escape(str(linha["status"]))

        def metrica(coluna: str, nome: str) -> str:
            valor = formatar_numero(linha.get(coluna), 1)
            return f"<div><b>{valor}</b><span>{nome}</span></div>"

        tiles.append(
            f'<div class="tile tile-{estado}"><div class="tile-topo">'
            f'<span class="tile-nome">{escape(str(linha["maquina"]))}</span>'
            f'<span class="tile-estado">{rotulo}</span></div>'
            f'<div class="tile-sub">{subtitulo}</div>'
            f'<div class="tile-met">{metrica("temperatura", "Temp. °C")}'
            f'{metrica("vibracao", "Vibração")}{metrica("pressao", "Pressão")}</div></div>'
        )
    return '<div class="grade">' + "".join(tiles) + "</div>"


def ir_para_criticos() -> None:
    st.session_state.pagina = "criticos"

def ir_para_simulacao() -> None:
    st.session_state.pagina = 'sim'


# ---------------------------------------------------------------------------
# Carga e navegação
# ---------------------------------------------------------------------------
if "versao_cache" not in st.session_state:
    st.session_state.versao_cache = 0
if "pagina" not in st.session_state:
    st.session_state.pagina = "geral"

df = carregar_dados(st.session_state.versao_cache)

if df.empty:
    st.warning("Ainda não há leituras no banco de dados ou a tabela 'leituras' não foi encontrada.")
    st.info("Mantenha o coletor.py em execução e confirme se ele está gravando na tabela leituras do MySQL.")
    st.stop()

todos_alertas = calcular_alertas(df)
qtd_criticos_total = len([a for a in todos_alertas if a["classificacao"] in CLASSIFICACOES_CRITICAS])

with st.sidebar:
    st.markdown(
        '<div class="marca"><div class="marca-nome">Monitoramento Industrial</div>'
        '<div class="marca-sub">Produção e condições operacionais</div></div>',
        unsafe_allow_html=True,
    )

    rotulos = {
        "geral": "Painel geral",
        "criticos": f"Alertas críticos ({qtd_criticos_total})" if qtd_criticos_total else "Alertas críticos",
        'sim': 'Simular cenário'
    }
    st.radio(
        "Navegação", list(rotulos), key="pagina",
        format_func=lambda chave: rotulos[chave], label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Filtros**")
    if st.button("Atualizar dados", use_container_width=True):
        st.session_state.versao_cache += 1
        st.rerun()

    maquinas_disponiveis = sorted(df["maquina"].dropna().unique().tolist())
    maquinas_selecionadas = st.multiselect("Máquinas", maquinas_disponiveis, default=maquinas_disponiveis)
    st.checkbox(
        "Ocultar períodos sem leitura", value=True, key="ocultar_lacunas",
        help=f"Remove dos gráficos os intervalos maiores que {int(LIMITE_LACUNA.total_seconds() // 60)} minutos sem nenhuma leitura.",
    )

    if st.session_state.pagina == "geral":
        status_disponiveis = sorted(df["status"].dropna().unique().tolist())
        status_selecionados = st.multiselect("Status", status_disponiveis, default=status_disponiveis)

        datas_validas = df["data_hora"].dropna()
        if not datas_validas.empty:
            data_min, data_max = datas_validas.min().date(), datas_validas.max().date()
            periodo = st.date_input(
                "Período das leituras", value=(data_min, data_max),
                min_value=data_min, max_value=data_max,
            )
        else:
            periodo = None

    st.caption("Dados consultados no MySQL da Clever Cloud. O cache é renovado a cada 5 segundos.")

alertas_atuais = [a for a in todos_alertas if a["maquina"] in maquinas_selecionadas]


# ---------------------------------------------------------------------------
# Página: Alertas críticos
# ---------------------------------------------------------------------------
def pagina_criticos() -> None:
    criticos = [a for a in alertas_atuais if a["classificacao"] in CLASSIFICACOES_CRITICAS]
    ultimas_gerais = ultimas_leituras(df).set_index("maquina")

    maquinas_afetadas = sorted({a["maquina"] for a in criticos})
    sem_comunicacao = len({a["maquina"] for a in criticos if a["classificacao"] == "Sem comunicação"})
    em_manutencao = len({a["maquina"] for a in criticos if a["classificacao"] == "Manutenção"})
    itens_criticos = len([a for a in criticos if a["classificacao"] != "Diagnóstico combinado"])

    subtitulo = "Máquinas que exigem ação imediata, calculadas na leitura mais recente de cada uma."
    if criticos:
        cabecalho("Alertas críticos", subtitulo,
                  f"{len(maquinas_afetadas)} máquina(s) em estado crítico", "crit", critico=True)
    else:
        cabecalho("Alertas críticos", subtitulo, "Nenhum alerta crítico", "ok")

    colunas = st.columns(4)
    cartoes = [
        ("Máquinas afetadas", formatar_numero(len(maquinas_afetadas)),
         f"de {formatar_numero(len(maquinas_selecionadas))} selecionadas", "crit" if maquinas_afetadas else "ok"),
        ("Alertas ativos", formatar_numero(itens_criticos), "indicadores fora da faixa crítica",
         "crit" if itens_criticos else "ok"),
        ("Sem comunicação", formatar_numero(sem_comunicacao), "sem leituras recentes",
         "warn" if sem_comunicacao else "ok"),
        ("Em manutenção", formatar_numero(em_manutencao), "manutenção recomendada",
         "warn" if em_manutencao else "ok"),
    ]
    for coluna, (rotulo, valor, detalhe, tom) in zip(colunas, cartoes):
        coluna.markdown(kpi(rotulo, valor, detalhe, tom), unsafe_allow_html=True)

    if not criticos:
        st.write("")
        st.markdown(
            '<div class="vazio"><b>Nenhum alerta crítico</b>'
            "<p>Todas as máquinas selecionadas estão dentro dos limites nas leituras mais recentes.</p></div>",
            unsafe_allow_html=True,
        )
        return

    secao("Máquinas em estado crítico")
    classes_presentes = [c for c in ORDEM_GRAVIDADE if any(a["classificacao"] == c for a in criticos)]
    escolhidas = st.multiselect("Tipos de alerta", classes_presentes, default=classes_presentes)
    criticos = [a for a in criticos if a["classificacao"] in escolhidas]
    if not criticos:
        st.info("Selecione ao menos um tipo de alerta para ver os detalhes.")
        return

    # Máquinas mais graves primeiro.
    por_maquina: dict[str, list[dict]] = {}
    for alerta in sorted(criticos, key=lambda a: (ORDEM_GRAVIDADE.get(a["classificacao"], 9), a["parametro"])):
        por_maquina.setdefault(alerta["maquina"], []).append(alerta)
    ordenadas = sorted(por_maquina, key=lambda m: (ORDEM_GRAVIDADE.get(por_maquina[m][0]["classificacao"], 9), m))

    esq, dir_ = st.columns(2)
    for i, maquina in enumerate(ordenadas):
        status = ultimas_gerais.at[maquina, "status"] if maquina in ultimas_gerais.index else "SEM STATUS"
        momento = ultimas_gerais.at[maquina, "data_hora"] if maquina in ultimas_gerais.index else None
        (esq if i % 2 == 0 else dir_).markdown(
            cartao_maquina(maquina, por_maquina[maquina], status, momento), unsafe_allow_html=True
        )

    # Investigação do histórico da máquina selecionada.
    secao("Investigar histórico")
    c1, c2 = st.columns(2)
    maquina_sel = c1.selectbox("Máquina", ordenadas)
    indicadores = [
        a["parametro"] for a in por_maquina[maquina_sel]
        if a["parametro"] in df.columns and a["parametro"] != "diagnostico"
    ]
    indicadores = list(dict.fromkeys(indicadores)) or [c for c in ("temperatura", "vibracao", "pressao") if c in df.columns]
    indicador = c2.selectbox("Indicador", indicadores)

    historico = (
        df[df["maquina"] == maquina_sel].dropna(subset=[indicador, "data_hora"])
        .sort_values("data_hora").tail(200)
    )
    with st.container(border=True):
        if historico.empty:
            st.info("Não há leituras desse indicador para a máquina selecionada.")
        else:
            fig = grafico_temporal(
                historico, indicador,
                f"{indicador.capitalize()} nas últimas {len(historico)} leituras de {maquina_sel}",
                indicador.capitalize(), altura=320, cor="#E5484D",
            )
            st.plotly_chart(fig, use_container_width=True)

    tabela = pd.DataFrame(criticos).rename(columns={
        "maquina": "Máquina", "parametro": "Indicador", "valor": "Valor observado",
        "unidade": "Unidade", "classificacao": "Classificação",
        "limite": "Regra / limite aplicado", "justificativa": "Justificativa",
    })
    st.download_button(
        "Exportar alertas críticos (CSV)",
        data=tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name="alertas_criticos.csv", mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Página: Painel geral
# ---------------------------------------------------------------------------
def pagina_geral() -> None:
    filtrado = df[
        df["maquina"].isin(maquinas_selecionadas) & df["status"].isin(status_selecionados)
    ].copy()

    if periodo and isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio = pd.Timestamp(periodo[0], tz="UTC")
        fim = pd.Timestamp(periodo[1], tz="UTC") + pd.Timedelta(days=1)
        filtrado = filtrado[filtrado["data_hora"].ge(inicio) & filtrado["data_hora"].lt(fim)]

    if filtrado.empty:
        st.warning("Nenhuma leitura encontrada para os filtros selecionados.")
        return

    ultimas = ultimas_leituras(filtrado)

    criticos = [a for a in alertas_atuais if a["classificacao"] in CLASSIFICACOES_CRITICAS]
    if criticos:
        chip, tom = f"{len({a['maquina'] for a in criticos})} máquina(s) em estado crítico", "crit"
    elif alertas_atuais:
        chip, tom = "Operação com atenção", "warn"
    else:
        chip, tom = "Operação normal", "ok"
    cabecalho(
        "Painel geral",
        "Acompanhamento de produção e condições operacionais das máquinas.",
        chip, tom,
    )

    maquinas_atencao = len({
        a["maquina"] for a in alertas_atuais
        if a["classificacao"] in ("Atenção", "Crítico", "Manutenção", "Sem comunicação", "Parada")
    })
    producao_atual = ultimas["producao"].sum(min_count=1)

    cols = st.columns(4)
    cols[0].markdown(kpi("Máquinas monitoradas", formatar_numero(filtrado["maquina"].nunique())), unsafe_allow_html=True)
    cols[1].markdown(kpi("Leituras no período", formatar_numero(len(filtrado))), unsafe_allow_html=True)
    cols[2].markdown(
        kpi("Máquinas em atenção", formatar_numero(maquinas_atencao), "com ao menos um alerta",
            "warn" if maquinas_atencao else "ok"),
        unsafe_allow_html=True,
    )
    cols[3].markdown(kpi("Produção registrada", formatar_numero(producao_atual), "soma das últimas leituras"),
                     unsafe_allow_html=True)

    # Grade de máquinas
    secao("Estado da planta")
    st.markdown(grade_maquinas(ultimas, alertas_atuais), unsafe_allow_html=True)

    # Alertas
    topo_a, topo_b = st.columns([4, 1])
    with topo_a:
        secao("Alertas e condições operacionais")
    if criticos:
        topo_b.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        topo_b.button("Ver alertas críticos", on_click=ir_para_criticos, use_container_width=True, type="primary")

    if alertas_atuais:
        alertas_ordenados = sorted(
            alertas_atuais,
            key=lambda a: (ORDEM_GRAVIDADE.get(a["classificacao"], 9), a["maquina"], a["parametro"]),
        )
        tabela_alertas = pd.DataFrame(alertas_ordenados).rename(columns={
            "maquina": "Máquina", "parametro": "Indicador", "valor": "Valor observado",
            "unidade": "Unidade", "classificacao": "Classificação",
            "limite": "Regra / limite aplicado", "justificativa": "Justificativa",
        })
        st.dataframe(tabela_alertas, use_container_width=True, hide_index=True)
        st.caption("Os alertas são recalculados a partir da leitura mais recente de cada máquina. "
                   "Leituras ausentes não são tratadas como zero.")
    else:
        st.success("Nenhuma regra de alerta foi acionada nas leituras mais recentes das máquinas selecionadas.")

    # Gráficos temporais
    secao("Evolução dos indicadores")

    def grafico_linha(coluna_dados: str, titulo: str, rotulo: str, vazio: str) -> None:
        with st.container(border=True):
            dados = filtrado.dropna(subset=[coluna_dados, "data_hora"])
            if dados.empty:
                st.info(vazio)
                return
            fig = grafico_temporal(dados, coluna_dados, titulo, rotulo)
            st.plotly_chart(fig, use_container_width=True)

    col_esq, col_dir = st.columns(2)
    with col_esq:
        grafico_linha("temperatura", "Temperatura por máquina", "Temperatura (°C)",
                      "Não há dados de temperatura no período selecionado.")
    with col_dir:
        grafico_linha("vibracao", "Vibração por máquina", "Vibração",
                      "Não há dados de vibração no período selecionado.")

    col_esq, col_dir = st.columns(2)
    with col_esq:
        grafico_linha("producao", "Produção registrada ao longo do tempo", "Produção",
                      "Não há dados de produção no período selecionado.")
    with col_dir:
        with st.container(border=True):
            status_df = ultimas.groupby("status", as_index=False).size().rename(columns={"size": "maquinas"})
            fig_status = px.pie(
                status_df, names="status", values="maquinas", hole=0.62,
                title="Distribuição do status atual", color_discrete_sequence=PALETA,
            )
            fig_status.update_traces(marker=dict(line=dict(color="#151C23", width=2)))
            st.plotly_chart(estilizar(fig_status, linhas=False), use_container_width=True)

    # Situação atual
    secao("Situação atual por máquina")
    colunas_status = [
        "maquina", "tipo", "status", "temperatura", "vibracao", "pressao",
        "producao", "ciclos", "defeitos", "desgaste", "data_hora",
    ]
    colunas_status = [c for c in colunas_status if c in ultimas.columns]
    tabela_status = ultimas[colunas_status].sort_values("maquina", na_position="last").rename(columns={
        "maquina": "Máquina", "tipo": "Tipo", "status": "Status", "temperatura": "Temperatura (°C)",
        "vibracao": "Vibração", "pressao": "Pressão", "producao": "Produção", "ciclos": "Ciclos",
        "defeitos": "Defeitos", "desgaste": "Desgaste", "data_hora": "Data/hora da leitura",
    })
    st.dataframe(tabela_status, use_container_width=True, hide_index=True)

    # Defeitos e desgaste, quando a API fornecer esses campos.
    col_esq, col_dir = st.columns(2)
    for coluna, (campo, titulo) in zip(
        (col_esq, col_dir),
        (("defeitos", "Defeitos na última leitura"), ("desgaste", "Desgaste na última leitura")),
    ):
        dados = ultimas.dropna(subset=[campo])
        if dados.empty:
            continue
        with coluna, st.container(border=True):
            fig = px.bar(
                dados.sort_values(campo, ascending=False), x="maquina", y=campo, title=titulo,
                labels={"maquina": "Máquina", campo: campo.capitalize()},
            )
            fig.update_traces(marker_color=PALETA[0])
            st.plotly_chart(estilizar(fig, 300, linhas=False), use_container_width=True)

    # Histórico e exportação
    with st.expander("Consultar histórico detalhado"):
        historico = filtrado.sort_values("data_hora", ascending=False).copy()
        historico["data_hora"] = historico["data_hora"].dt.strftime("%d/%m/%Y %H:%M:%S UTC")
        colunas_historico = [
            "id", "id_api", "data_hora", "maquina", "tipo", "temperatura",
            "vibracao", "pressao", "producao", "ciclos", "defeitos", "desgaste", "status",
        ]
        colunas_historico = [c for c in colunas_historico if c in historico.columns]
        st.dataframe(historico[colunas_historico], use_container_width=True, hide_index=True)
        st.download_button(
            "Exportar histórico em CSV",
            data=historico[colunas_historico].to_csv(index=False).encode("utf-8-sig"),
            file_name="historico_monitoramento.csv", mime="text/csv",
        )


if st.session_state.pagina == "criticos":
    pagina_criticos()
else:
    pagina_geral()

st.markdown(
    f'<div class="rodape">Banco de dados: MySQL – Clever Cloud  ·  '
    f'Última atualização da página: {pd.Timestamp.now().strftime("%d/%m/%Y %H:%M:%S")}</div>',
    unsafe_allow_html=True,
)

def pagina_sim() -> None:
    filtrado = df[
        df["maquina"].isin(maquinas_selecionadas) & df["status"].isin(status_selecionados)
    ].copy()

    if periodo and isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio = pd.Timestamp(periodo[0], tz="UTC")
        fim = pd.Timestamp(periodo[1], tz="UTC") + pd.Timedelta(days=1)
        filtrado = filtrado[filtrado["data_hora"].ge(inicio) & filtrado["data_hora"].lt(fim)]

    if filtrado.empty:
        st.warning("Nenhuma leitura encontrada para os filtros selecionados.")
        return

    ultimas = ultimas_leituras(filtrado)

    criticos = [a for a in alertas_atuais if a["classificacao"] in CLASSIFICACOES_CRITICAS]
    if criticos:
        chip, tom = f"{len({a['maquina'] for a in criticos})} máquina(s) em estado crítico", "crit"
    elif alertas_atuais:
        chip, tom = "Operação com atenção", "warn"
    else:
        chip, tom = "Operação normal", "ok"
    cabecalho(
        "Painel geral",
        "Acompanhamento de produção e condições operacionais das máquinas.",
        chip, tom,
    )

    maquinas_atencao = len({
        a["maquina"] for a in alertas_atuais
        if a["classificacao"] in ("Atenção", "Crítico", "Manutenção", "Sem comunicação", "Parada")
    })
    producao_atual = ultimas["producao"].sum(min_count=1)

    cols = st.columns(4)
    cols[0].markdown(kpi("Máquinas monitoradas", formatar_numero(filtrado["maquina"].nunique())), unsafe_allow_html=True)
    cols[1].markdown(kpi("Leituras no período", formatar_numero(len(filtrado))), unsafe_allow_html=True)
    cols[2].markdown(
        kpi("Máquinas em atenção", formatar_numero(maquinas_atencao), "com ao menos um alerta",
            "warn" if maquinas_atencao else "ok"),
        unsafe_allow_html=True,
    )
    cols[3].markdown(kpi("Produção registrada", formatar_numero(producao_atual), "soma das últimas leituras"),
                     unsafe_allow_html=True)

    # Grade de máquinas
    secao("Estado da planta")
    st.markdown(grade_maquinas(ultimas, alertas_atuais), unsafe_allow_html=True)

    # Alertas
    topo_a, topo_b = st.columns([4, 1])
    with topo_a:
        secao("Alertas e condições operacionais")
    if criticos:
        topo_b.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        topo_b.button("Ver alertas críticos", on_click=ir_para_criticos, use_container_width=True, type="primary")

    if alertas_atuais:
        alertas_ordenados = sorted(
            alertas_atuais,
            key=lambda a: (ORDEM_GRAVIDADE.get(a["classificacao"], 9), a["maquina"], a["parametro"]),
        )
        tabela_alertas = pd.DataFrame(alertas_ordenados).rename(columns={
            "maquina": "Máquina", "parametro": "Indicador", "valor": "Valor observado",
            "unidade": "Unidade", "classificacao": "Classificação",
            "limite": "Regra / limite aplicado", "justificativa": "Justificativa",
        })
        st.dataframe(tabela_alertas, use_container_width=True, hide_index=True)
        st.caption("Os alertas são recalculados a partir da leitura mais recente de cada máquina. "
                   "Leituras ausentes não são tratadas como zero.")
    else:
        st.success("Nenhuma regra de alerta foi acionada nas leituras mais recentes das máquinas selecionadas.")

    # Gráficos temporais
    secao("Evolução dos indicadores")