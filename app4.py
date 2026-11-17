from __future__ import annotations

import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import inspect, text

from database.connection import engine
from rules.regras_industriais import (
    avaliar_maquinas,
    REGRAS,
    ALIASES,
    FAIXAS_NORMAIS,
)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Monitoramento Industrial",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETA = ["#3FA7C9", "#F5A524", "#3DB87A", "#9A8CE8", "#E5688A", "#8796A3"]

TONS = {
    "Sem comunicação": ("#B4C0CA", "rgba(135,150,163,.18)"),
    "Manutenção": ("#FFB067", "rgba(255,150,50,.16)"),
    "Crítico": ("#FF7B80", "rgba(229,72,77,.18)"),
    "Parada": ("#F5C451", "rgba(245,165,36,.16)"),
    "Atenção": ("#F5C451", "rgba(245,165,36,.16)"),
    "Diagnóstico combinado": ("#FF9AA0", "rgba(229,72,77,.26)"),
}

ORDEM_GRAVIDADE = {
    "Sem comunicação": 0,
    "Manutenção": 1,
    "Crítico": 2,
    "Diagnóstico combinado": 3,
    "Parada": 4,
    "Atenção": 5,
}

CLASSIFICACOES_CRITICAS = (
    "Sem comunicação",
    "Manutenção",
    "Crítico",
    "Diagnóstico combinado",
)

LIMITE_LACUNA = pd.Timedelta(minutes=30)


def carregar_css() -> None:
    caminho_css = Path(__file__).resolve().parent / "styles" / "style.css"
    if caminho_css.exists():
        css = caminho_css.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


carregar_css()


# ---------------------------------------------------------------------------
# Tratamento e carga dos dados
# ---------------------------------------------------------------------------
def calcular_producao_por_intervalo(df: pd.DataFrame) -> pd.DataFrame:
    """
    A API fornece produção acumulada. Esta função preserva o contador original
    e transforma 'producao' na quantidade produzida desde a leitura anterior.

    Quando o contador reinicia (diferença negativa), considera o valor atual
    como produção desde o reinício. A primeira leitura fica nula porque não
    existe leitura anterior para calcular a diferença.
    """
    df = df.copy()
    df["producao_acumulada"] = pd.to_numeric(
        df["producao"], errors="coerce"
    )
    df["producao"] = float("nan")

    if "data_hora" not in df.columns:
        return df

    for _, indices in df.groupby("maquina", sort=False).groups.items():
        grupo = df.loc[indices].sort_values("data_hora")
        acumulada = grupo["producao_acumulada"]
        diferenca = acumulada.diff()

        # Se o contador reiniciar, a diferença negativa não representa
        # produção negativa: o valor atual passa a ser a produção do intervalo.
        reinicio = diferenca < 0
        diferenca.loc[reinicio] = acumulada.loc[reinicio]

        df.loc[grupo.index, "producao"] = diferenca

    return df


@st.cache_data(ttl=5, show_spinner=False)
def carregar_dados(ultima_atualizacao: int) -> pd.DataFrame:
    """Carrega, remove duplicidades e trata os dados históricos do MySQL."""
    del ultima_atualizacao

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
                ORDER BY timestamp_api, maquina, id
            """),
            conexao,
        )

    if df.empty:
        return df

    # Uma máquina deve ter somente uma leitura por timestamp da API.
    # O registro com maior id local é mantido em caso de duplicidade.
    df = df.sort_values("id").drop_duplicates(
        subset=["maquina", "timestamp_api"],
        keep="last",
    ).copy()

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
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    df["maquina"] = df["maquina"].fillna("Máquina não identificada")
    df["status"] = df["status"].fillna("SEM STATUS").astype(str).str.upper()

    # Calcula a produção incremental depois de ordenar/deduplicar as leituras.
    df = df.sort_values(["maquina", "data_hora", "id"]).reset_index(drop=True)
    df = calcular_producao_por_intervalo(df)

    return df


def ultimas_leituras(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.dropna(subset=["data_hora"])
        .sort_values("data_hora")
        .groupby("maquina", as_index=False)
        .tail(1)
    )


def calcular_alertas(df: pd.DataFrame) -> list[dict]:
    alertas = avaliar_maquinas(
        ultimas_leituras(df).to_dict(orient="records")
    )

    for maquina in sorted({a["maquina"] for a in alertas}):
        indicadores = {
            a["parametro"]
            for a in alertas
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
                "justificativa": (
                    "Indicadores afetados: "
                    + ", ".join(sorted(indicadores))
                    + "."
                ),
            })

    return alertas


# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------
def formatar_numero(valor, casas: int = 2) -> str:
    if valor is None or pd.isna(valor):
        return "-"
    try:
        valor = float(str(valor).replace(",", "."))
    except (ValueError, TypeError):
        return str(valor)
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tempo_desde(momento) -> str:
    if momento is None or pd.isna(momento):
        return "horário desconhecido"
    minutos = int(
        (pd.Timestamp.now(tz="UTC") - momento).total_seconds() // 60
    )
    if minutos < 1:
        return "agora há pouco"
    if minutos < 60:
        return f"há {minutos} min"
    if minutos < 1440:
        return f"há {minutos // 60} h"
    return f"há {minutos // 1440} d"


def cabecalho(
    titulo: str,
    subtitulo: str,
    chip: str,
    tom_chip: str,
    critico: bool = False,
) -> None:
    classe = "topo alerta" if critico else "topo"
    st.markdown(
        f'<div class="{classe}"><div><h1>{escape(titulo)}</h1>'
        f'<p>{escape(subtitulo)}</p></div>'
        f'<span class="chip chip-{tom_chip}"><i></i>{escape(chip)}</span></div>',
        unsafe_allow_html=True,
    )


def secao(titulo: str) -> None:
    st.markdown(
        f'<div class="secao">{escape(titulo)}</div>',
        unsafe_allow_html=True,
    )


def kpi(rotulo: str, valor: str, detalhe: str = "", tom: str = "neutro") -> str:
    return (
        f'<div class="kpi kpi-{tom}"><div class="kpi-rot">{escape(rotulo)}</div>'
        f'<div class="kpi-val">{escape(valor)}</div>'
        f'<div class="kpi-det">{escape(detalhe)}</div></div>'
    )


def estilizar(fig, altura: int = 340, linhas: bool = True):
    fig.update_layout(
        template="plotly_white",
        height=altura,
        colorway=PALETA,
        font=dict(family="IBM Plex Sans, sans-serif", color="#475569", size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=52, b=10),
        title=dict(font=dict(size=14, color="#1E293B"), x=0),
        legend=dict(orientation="h", y=-0.22, title_text=""),
        hovermode="x unified" if linhas else "closest",
    )
    fig.update_xaxes(gridcolor="#E2E8F0", linecolor="#CBD5E1", title_text=None)
    fig.update_yaxes(gridcolor="#E2E8F0", linecolor="#CBD5E1")
    return fig


def inserir_quebras(dados: pd.DataFrame, coluna: str) -> pd.DataFrame:
    dados = dados[["data_hora", "maquina", coluna]].copy()
    dados["data_hora"] = dados["data_hora"].dt.tz_convert(None)
    partes = []

    for _, grupo in dados.sort_values("data_hora").groupby("maquina", sort=False):
        anterior = grupo["data_hora"].shift(1)
        pausa = (grupo["data_hora"] - anterior) > LIMITE_LACUNA
        quebras = grupo.loc[pausa].copy()
        quebras["data_hora"] = anterior[pausa] + pd.Timedelta(seconds=1)
        quebras[coluna] = float("nan")
        partes.append(pd.concat([grupo, quebras]))

    if not partes:
        return dados
    return (
        pd.concat(partes)
        .sort_values(["maquina", "data_hora"])
        .reset_index(drop=True)
    )


def eixo_comprimido(datas: pd.Series):
    t = datas.dropna().drop_duplicates().sort_values().reset_index(drop=True)
    origem = t.iloc[0]
    passos = t.diff()
    lacunas = [
        (t[i - 1], t[i])
        for i in t.index[passos > LIMITE_LACUNA]
    ]
    ativo = passos[passos <= LIMITE_LACUNA].sum().total_seconds()
    visual = max(ativo * 0.02, 1.0)

    def x_de(serie: pd.Series) -> pd.Series:
        x = (serie - origem).dt.total_seconds()
        for ini, fim in lacunas:
            x = x - (serie >= fim) * (
                (fim - ini).total_seconds() - visual
            )
        return x

    def x_escalar(momento: pd.Timestamp) -> float:
        return float(x_de(pd.Series([momento])).iloc[0])

    def real_de(posicao: float) -> pd.Timestamp:
        extra = sum(
            (fim - ini).total_seconds() - visual
            for ini, fim in lacunas
            if posicao >= x_escalar(fim)
        )
        return origem + pd.Timedelta(seconds=posicao + extra)

    return x_escalar, x_de, real_de, lacunas, visual, x_escalar(t.iloc[-1])


def grafico_temporal(
    dados: pd.DataFrame,
    coluna: str,
    titulo: str,
    rotulo: str,
    altura: int = 340,
    cor: str | None = None,
):
    serie = inserir_quebras(dados, coluna)
    rotulos = {
        "data_hora": "Data/hora",
        "x": "Data/hora",
        coluna: rotulo,
        "maquina": "Máquina",
    }

    def grafico_eixo_real():
        fig = px.line(
            serie,
            x="data_hora",
            y=coluna,
            color="maquina",
            title=titulo,
            labels=rotulos,
        )
        fig.update_traces(connectgaps=False)
        if cor:
            fig.update_traces(
                line_color=cor,
                marker_color=cor,
                mode="markers",
            )
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

        fig = px.line(
            serie,
            x="x",
            y=coluna,
            color="maquina",
            title=titulo,
            labels=rotulos,
            custom_data=["hora_real"],
        )
        fig.update_traces(
            connectgaps=False,
            hovertemplate=(
                "%{customdata[0]}<br>%{y:.2f}"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        if cor:
            fig.update_traces(line_color=cor, marker_color=cor)

        estilizar(fig, altura, linhas=False)

        zonas = []
        for ini, fim in lacunas:
            inicio_faixa = x_escalar(ini)
            zonas.append((inicio_faixa, inicio_faixa + visual))
            fig.add_shape(
                type="rect",
                xref="x",
                yref="paper",
                x0=inicio_faixa,
                x1=inicio_faixa + visual,
                y0=0,
                y1=1,
                fillcolor="#2E3B47",
                opacity=0.7,
                line_width=0,
                layer="below",
            )

        posicoes = (
            [x_max * k / 5 for k in range(6)]
            if x_max > 0 else [0.0]
        )
        posicoes = [
            float(p)
            for p in posicoes
            if not any(a < p < b for a, b in zonas)
        ]
        margem = max(x_max * 0.01, 1.0)

        fig.update_xaxes(
            type="linear",
            range=[-margem, x_max + margem],
            tickmode="array",
            tickvals=posicoes,
            ticktext=[
                real_de(p).strftime("%d/%m %H:%M")
                for p in posicoes
            ],
        )
        return fig

    except Exception as erro:
        st.caption(
            f"Eixo sem lacunas indisponível ({type(erro).__name__}: {erro}). "
            "Exibindo o eixo de tempo real."
        )
        return grafico_eixo_real()


def pill(classificacao: str) -> str:
    cor, fundo = TONS.get(
        classificacao,
        ("#B4C0CA", "rgba(135,150,163,.18)"),
    )
    return (
        f'<span class="pill" style="color:{cor};background:{fundo}">'
        f'{escape(classificacao)}</span>'
    )


def cartao_maquina(
    maquina: str,
    alertas: list[dict],
    status: str,
    momento,
) -> str:
    linhas = []

    for alerta in alertas:
        valor = ""
        if alerta.get("valor") is not None and not pd.isna(alerta["valor"]):
            valor = (
                f'{formatar_numero(alerta["valor"], 2)} '
                f'{escape(str(alerta.get("unidade") or ""))}'
            ).strip()

        linhas.append(
            '<div class="alerta-linha"><div class="alerta-cab">'
            f'<span class="alerta-ind">{escape(str(alerta["parametro"]).replace("_", " "))}</span>'
            f'<span>{pill(alerta["classificacao"])}'
            f'<span class="alerta-val">{valor}</span></span></div>'
            f'<div class="alerta-regra">Regra: {escape(str(alerta.get("limite") or "—"))}</div>'
            f'<div class="alerta-just">{escape(str(alerta.get("justificativa") or ""))}</div>'
            '</div>'
        )

    return (
        '<div class="maq"><div class="maq-topo"><div>'
        f'<div class="maq-nome">{escape(maquina)}</div>'
        f'<div class="maq-meta">Última leitura {escape(tempo_desde(momento))}</div>'
        f'</div><span class="maq-status">{escape(status)}</span></div>'
        + "".join(linhas)
        + "</div>"
    )


def grade_maquinas(ultimas: pd.DataFrame, alertas: list[dict]) -> str:
    classes_por_maquina: dict[str, list[str]] = {}

    for alerta in alertas:
        classes_por_maquina.setdefault(alerta["maquina"], []).append(
            alerta["classificacao"]
        )

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
        subtitulo = (
            f'{escape(str(tipo))}  ·  '
            if isinstance(tipo, str) and tipo
            else ""
        ) + escape(str(linha["status"]))

        def metrica(coluna: str, nome: str) -> str:
            valor = formatar_numero(linha.get(coluna), 1)
            return f"<div><b>{valor}</b><span>{nome}</span></div>"

        tiles.append(
            f'<div class="tile tile-{estado}"><div class="tile-topo">'
            f'<span class="tile-nome">{escape(str(linha["maquina"]))}</span>'
            f'<span class="tile-estado">{rotulo}</span></div>'
            f'<div class="tile-sub">{subtitulo}</div>'
            f'<div class="tile-met">'
            f'{metrica("temperatura", "Temp. °C")}'
            f'{metrica("vibracao", "Vibração")}'
            f'{metrica("pressao", "Pressão")}'
            '</div></div>'
        )

    return '<div class="grade">' + "".join(tiles) + "</div>"


def ir_para_criticos() -> None:
    st.session_state.pagina = "criticos"


# ---------------------------------------------------------------------------
# Carga inicial e navegação
# ---------------------------------------------------------------------------
if "versao_cache" not in st.session_state:
    st.session_state.versao_cache = 0
if "pagina" not in st.session_state:
    st.session_state.pagina = "geral"

df = carregar_dados(st.session_state.versao_cache)

if df.empty:
    st.warning(
        "Ainda não há leituras no banco de dados ou a tabela 'leituras' "
        "não foi encontrada."
    )
    st.info(
        "Mantenha o coletor.py em execução e confirme se ele está gravando "
        "na tabela leituras do MySQL."
    )
    st.stop()

todos_alertas = calcular_alertas(df)
qtd_criticos_total = sum(
    a["classificacao"] in CLASSIFICACOES_CRITICAS
    for a in todos_alertas
)

with st.sidebar:
    st.markdown(
        '<div class="marca"><div class="marca-nome">Monitoramento Industrial</div>'
        '<div class="marca-sub">Produção e condições operacionais</div></div>',
        unsafe_allow_html=True,
    )

    rotulos = {
        "geral": "Painel geral",
        "criticos": (
            f"Alertas críticos ({qtd_criticos_total})"
            if qtd_criticos_total else "Alertas críticos"
        ),
        "simulacao": "Análise de médias",
    }

    st.radio(
        "Navegação",
        list(rotulos),
        key="pagina",
        format_func=lambda chave: rotulos[chave],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Filtros**")

    if st.button("Atualizar dados", use_container_width=True):
        st.session_state.versao_cache += 1
        st.rerun()

    maquinas_disponiveis = sorted(df["maquina"].dropna().unique().tolist())
    maquinas_selecionadas = st.multiselect(
        "Máquinas",
        maquinas_disponiveis,
        default=maquinas_disponiveis,
    )

    st.checkbox(
        "Ocultar períodos sem leitura",
        value=True,
        key="ocultar_lacunas",
        help=(
            "Remove dos gráficos os intervalos maiores que "
            f"{int(LIMITE_LACUNA.total_seconds() // 60)} minutos sem leitura."
        ),
    )

    if st.session_state.pagina == "geral":
        status_disponiveis = sorted(df["status"].dropna().unique().tolist())
        status_selecionados = st.multiselect(
            "Status",
            status_disponiveis,
            default=status_disponiveis,
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

    st.caption(
        "Dados consultados no MySQL da Clever Cloud. "
        "O cache é renovado a cada 5 segundos."
    )

alertas_atuais = [
    a for a in todos_alertas
    if a["maquina"] in maquinas_selecionadas
]


# ---------------------------------------------------------------------------
# Página: Alertas críticos
# ---------------------------------------------------------------------------
def pagina_criticos() -> None:
    criticos = [
        a for a in alertas_atuais
        if a["classificacao"] in CLASSIFICACOES_CRITICAS
    ]
    ultimas_gerais = ultimas_leituras(df).set_index("maquina")
    maquinas_afetadas = sorted({a["maquina"] for a in criticos})
    sem_comunicacao = len({
        a["maquina"] for a in criticos
        if a["classificacao"] == "Sem comunicação"
    })
    em_manutencao = len({
        a["maquina"] for a in criticos
        if a["classificacao"] == "Manutenção"
    })
    itens_criticos = len([
        a for a in criticos
        if a["classificacao"] != "Diagnóstico combinado"
    ])

    subtitulo = (
        "Máquinas que exigem ação imediata, calculadas na leitura "
        "mais recente de cada uma."
    )

    if criticos:
        cabecalho(
            "Alertas críticos",
            subtitulo,
            f"{len(maquinas_afetadas)} máquina(s) em estado crítico",
            "crit",
            critico=True,
        )
    else:
        cabecalho(
            "Alertas críticos",
            subtitulo,
            "Nenhum alerta crítico",
            "ok",
        )

    colunas = st.columns(4)
    cartoes = [
        (
            "Máquinas afetadas",
            formatar_numero(len(maquinas_afetadas)),
            f"de {formatar_numero(len(maquinas_selecionadas))} selecionadas",
            "crit" if maquinas_afetadas else "ok",
        ),
        (
            "Alertas ativos",
            formatar_numero(itens_criticos),
            "indicadores fora da faixa crítica",
            "crit" if itens_criticos else "ok",
        ),
        (
            "Sem comunicação",
            formatar_numero(sem_comunicacao),
            "sem leituras recentes",
            "warn" if sem_comunicacao else "ok",
        ),
        (
            "Em manutenção",
            formatar_numero(em_manutencao),
            "manutenção recomendada",
            "warn" if em_manutencao else "ok",
        ),
    ]

    for coluna, (rotulo, valor, detalhe, tom) in zip(colunas, cartoes):
        coluna.markdown(
            kpi(rotulo, valor, detalhe, tom),
            unsafe_allow_html=True,
        )

    if not criticos:
        st.write("")
        st.markdown(
            '<div class="vazio"><b>Nenhum alerta crítico</b>'
            '<p>Todas as máquinas selecionadas estão dentro dos limites '
            'nas leituras mais recentes.</p></div>',
            unsafe_allow_html=True,
        )
        return

    secao("Máquinas em estado crítico")
    classes_presentes = [
        c for c in ORDEM_GRAVIDADE
        if any(a["classificacao"] == c for a in criticos)
    ]
    escolhidas = st.multiselect(
        "Tipos de alerta",
        classes_presentes,
        default=classes_presentes,
    )
    criticos = [
        a for a in criticos
        if a["classificacao"] in escolhidas
    ]

    if not criticos:
        st.info("Selecione ao menos um tipo de alerta para ver os detalhes.")
        return

    por_maquina: dict[str, list[dict]] = {}
    for alerta in sorted(
        criticos,
        key=lambda a: (
            ORDEM_GRAVIDADE.get(a["classificacao"], 9),
            a["parametro"],
        ),
    ):
        por_maquina.setdefault(alerta["maquina"], []).append(alerta)

    ordenadas = sorted(
        por_maquina,
        key=lambda m: (
            ORDEM_GRAVIDADE.get(
                por_maquina[m][0]["classificacao"], 9
            ),
            m,
        ),
    )

    esq, dir_ = st.columns(2)
    for i, maquina in enumerate(ordenadas):
        status = (
            ultimas_gerais.at[maquina, "status"]
            if maquina in ultimas_gerais.index
            else "SEM STATUS"
        )
        momento = (
            ultimas_gerais.at[maquina, "data_hora"]
            if maquina in ultimas_gerais.index
            else None
        )
        (esq if i % 2 == 0 else dir_).markdown(
            cartao_maquina(maquina, por_maquina[maquina], status, momento),
            unsafe_allow_html=True,
        )

    secao("Investigar histórico")
    c1, c2 = st.columns(2)
    maquina_sel = c1.selectbox("Máquina", ordenadas)
    indicadores = [
        a["parametro"]
        for a in por_maquina[maquina_sel]
        if a["parametro"] in df.columns
        and a["parametro"] != "diagnostico"
    ]
    indicadores = list(dict.fromkeys(indicadores)) or [
        c for c in ("temperatura", "vibracao", "pressao")
        if c in df.columns
    ]
    indicador = c2.selectbox("Indicador", indicadores)

    historico = (
        df[df["maquina"] == maquina_sel]
        .dropna(subset=[indicador, "data_hora"])
        .sort_values("data_hora")
        .tail(200)
    )

    with st.container(border=True):
        if historico.empty:
            st.info("Não há leituras desse indicador para a máquina selecionada.")
        else:
            fig = grafico_temporal(
                historico,
                indicador,
                f"{indicador.capitalize()} nas últimas "
                f"{len(historico)} leituras de {maquina_sel}",
                indicador.capitalize(),
                altura=320,
                cor="#E5484D",
            )
            st.plotly_chart(fig, use_container_width=True)

    tabela = pd.DataFrame(criticos).rename(columns={
        "maquina": "Máquina",
        "parametro": "Indicador",
        "valor": "Valor observado",
        "unidade": "Unidade",
        "classificacao": "Classificação",
        "limite": "Regra / limite aplicado",
        "justificativa": "Justificativa",
    })

    st.download_button(
        "Exportar alertas críticos (CSV)",
        data=tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name="alertas_criticos.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Página: Painel geral
# ---------------------------------------------------------------------------
def pagina_geral() -> None:
    filtrado = df[
        df["maquina"].isin(maquinas_selecionadas)
        & df["status"].isin(status_selecionados)
    ].copy()

    if periodo and isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        inicio = pd.Timestamp(periodo[0], tz="UTC")
        fim = pd.Timestamp(periodo[1], tz="UTC") + pd.Timedelta(days=1)
        filtrado = filtrado[
            filtrado["data_hora"].ge(inicio)
            & filtrado["data_hora"].lt(fim)
        ]

    if filtrado.empty:
        st.warning("Nenhuma leitura encontrada para os filtros selecionados.")
        return

    ultimas = ultimas_leituras(filtrado)
    criticos = [
        a for a in alertas_atuais
        if a["classificacao"] in CLASSIFICACOES_CRITICAS
    ]

    if criticos:
        chip = (
            f"{len({a['maquina'] for a in criticos})} "
            "máquina(s) em estado crítico"
        )
        tom = "crit"
    elif alertas_atuais:
        chip, tom = "Operação com atenção", "warn"
    else:
        chip, tom = "Operação normal", "ok"

    cabecalho(
        "Painel geral",
        "Acompanhamento de produção e condições operacionais das máquinas.",
        chip,
        tom,
    )

    maquinas_atencao = len({
        a["maquina"] for a in alertas_atuais
        if a["classificacao"] in (
            "Atenção", "Crítico", "Manutenção",
            "Sem comunicação", "Parada",
        )
    })

    # Soma a produção incremental dos intervalos no período filtrado.
    producao_total = filtrado["producao"].sum(min_count=1)

    cols = st.columns(4)
    cols[0].markdown(
        kpi("Máquinas monitoradas", formatar_numero(filtrado["maquina"].nunique())),
        unsafe_allow_html=True,
    )
    cols[1].markdown(
        kpi("Leituras no período", formatar_numero(len(filtrado))),
        unsafe_allow_html=True,
    )
    cols[2].markdown(
        kpi(
            "Máquinas em atenção",
            formatar_numero(maquinas_atencao),
            "com ao menos um alerta",
            "warn" if maquinas_atencao else "ok",
        ),
        unsafe_allow_html=True,
    )
    cols[3].markdown(
        kpi(
            "Produção no período",
            formatar_numero(producao_total),
            "soma das diferenças entre leituras",
        ),
        unsafe_allow_html=True,
    )

    secao("Estado da planta")
    st.markdown(
        grade_maquinas(ultimas, alertas_atuais),
        unsafe_allow_html=True,
    )

    topo_a, topo_b = st.columns([4, 1])
    with topo_a:
        secao("Alertas e condições operacionais")

    if criticos:
        topo_b.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
        topo_b.button(
            "Ver alertas críticos",
            on_click=ir_para_criticos,
            use_container_width=True,
            type="primary",
        )

    if alertas_atuais:
        alertas_ordenados = sorted(
            alertas_atuais,
            key=lambda a: (
                ORDEM_GRAVIDADE.get(a["classificacao"], 9),
                a["maquina"],
                a["parametro"],
            ),
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
        st.dataframe(
            tabela_alertas,
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Os alertas são recalculados a partir da leitura mais recente "
            "de cada máquina. Leituras ausentes não são tratadas como zero."
        )
    else:
        st.success(
            "Nenhuma regra de alerta foi acionada nas leituras mais recentes "
            "das máquinas selecionadas."
        )

    secao("Evolução dos indicadores")

    def grafico_linha(
        coluna_dados: str,
        titulo: str,
        rotulo: str,
        vazio: str,
    ) -> None:
        with st.container(border=True):
            dados_grafico = filtrado.dropna(
                subset=[coluna_dados, "data_hora"]
            )
            if dados_grafico.empty:
                st.info(vazio)
                return
            fig = grafico_temporal(
                dados_grafico,
                coluna_dados,
                titulo,
                rotulo,
            )
            st.plotly_chart(fig, use_container_width=True)

    col_esq, col_dir = st.columns(2)
    with col_esq:
        grafico_linha(
            "temperatura",
            "Temperatura por máquina",
            "Temperatura (°C)",
            "Não há dados de temperatura no período selecionado.",
        )
    with col_dir:
        grafico_linha(
            "vibracao",
            "Vibração por máquina",
            "Vibração",
            "Não há dados de vibração no período selecionado.",
        )

    col_esq, col_dir = st.columns(2)
    with col_esq:
        grafico_linha(
            "producao",
            "Produção por intervalo ao longo do tempo",
            "Produção no intervalo",
            "Não há dados suficientes para calcular a produção por intervalo.",
        )
    with col_dir:
        with st.container(border=True):
            status_df = (
                ultimas.groupby("status", as_index=False)
                .size()
                .rename(columns={"size": "maquinas"})
            )
            fig_status = px.pie(
                status_df,
                names="status",
                values="maquinas",
                hole=0.62,
                title="Distribuição do status atual",
                color_discrete_sequence=PALETA,
            )
            fig_status.update_traces(
                marker=dict(line=dict(color="#151C23", width=2))
            )
            st.plotly_chart(
                estilizar(fig_status, linhas=False),
                use_container_width=True,
            )

    secao("Situação atual por máquina")
    colunas_status = [
        "maquina", "tipo", "status", "temperatura", "vibracao",
        "pressao", "producao_acumulada", "producao", "ciclos",
        "defeitos", "desgaste", "data_hora",
    ]
    colunas_status = [
        c for c in colunas_status
        if c in ultimas.columns
    ]
    tabela_status = ultimas[colunas_status].sort_values(
        "maquina"
    ).rename(columns={
        "maquina": "Máquina",
        "tipo": "Tipo",
        "status": "Status",
        "temperatura": "Temperatura (°C)",
        "vibracao": "Vibração",
        "pressao": "Pressão",
        "producao_acumulada": "Produção acumulada",
        "producao": "Produção no último intervalo",
        "ciclos": "Ciclos",
        "defeitos": "Defeitos",
        "desgaste": "Desgaste",
        "data_hora": "Data/hora da leitura",
    })
    st.dataframe(
        tabela_status,
        use_container_width=True,
        hide_index=True,
    )

    col_esq, col_dir = st.columns(2)
    for coluna, (campo, titulo) in zip(
        (col_esq, col_dir),
        (
            ("defeitos", "Defeitos na última leitura"),
            ("desgaste", "Desgaste na última leitura"),
        ),
    ):
        dados_barra = ultimas.dropna(subset=[campo])
        if dados_barra.empty:
            continue
        with coluna, st.container(border=True):
            fig = px.bar(
                dados_barra.sort_values(campo, ascending=False),
                x="maquina",
                y=campo,
                title=titulo,
                labels={"maquina": "Máquina", campo: campo.capitalize()},
            )
            fig.update_traces(marker_color=PALETA[0])
            st.plotly_chart(
                estilizar(fig, 300, linhas=False),
                use_container_width=True,
            )

    with st.expander("Consultar histórico detalhado"):
        historico = filtrado.sort_values(
            "data_hora", ascending=False
        ).copy()
        historico["data_hora"] = historico["data_hora"].dt.strftime(
            "%d/%m/%Y %H:%M:%S UTC"
        )
        colunas_historico = [
            "id", "id_api", "data_hora", "maquina", "tipo",
            "temperatura", "vibracao", "pressao",
            "producao_acumulada", "producao",
            "ciclos", "defeitos", "desgaste", "status",
        ]
        colunas_historico = [
            c for c in colunas_historico
            if c in historico.columns
        ]
        st.dataframe(
            historico[colunas_historico],
            use_container_width=True,
            hide_index=True,
        )
        st.download_button(
            "Exportar histórico em CSV",
            data=historico[colunas_historico].to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name="historico_monitoramento.csv",
            mime="text/csv",
        )


def gerar_previsao_emergencial(
    dados: pd.DataFrame,
    duracao_horas: float,
) -> pd.DataFrame:
    """
    Estima a produção de todas as máquinas usando taxas históricas observadas
    quando a máquina estava OPERANDO e seus indicadores estavam dentro das
    faixas operacionais cadastradas em FAIXAS_NORMAIS.

    P25 = cenário conservador; P90 = cenário de alto desempenho.
    A estimativa não presume uma relação física entre sensores e produção:
    utiliza a produção real por hora observada no histórico.
    """
    if dados.empty:
        return pd.DataFrame()

    resultados = []

    for maquina in sorted(dados["maquina"].dropna().unique()):
        historico = (
            dados[dados["maquina"] == maquina]
            .dropna(subset=["data_hora"])
            .sort_values("data_hora")
            .copy()
        )
        if historico.empty:
            continue

        ultima = historico.iloc[-1]
        status_atual = str(ultima.get("status", "Não informado")).upper()

        regras_maquina = [
            (parametro, faixa)
            for (nome_maquina, parametro), faixa in FAIXAS_NORMAIS.items()
            if nome_maquina == maquina
        ]

        dentro_limites = pd.Series(True, index=historico.index)
        limites_texto = []
        parametros_sem_dados = []

        if not regras_maquina:
            dentro_limites[:] = False

        for parametro, faixa in regras_maquina:
            aliases = ALIASES.get(parametro, (parametro,))
            coluna = next(
                (
                    nome for nome in aliases
                    if nome in historico.columns
                    and pd.to_numeric(
                        historico[nome], errors="coerce"
                    ).notna().any()
                ),
                None,
            )

            minimo = faixa.get("min")
            maximo = faixa.get("max")

            partes_limite = []
            if minimo is not None:
                operador = ">=" if faixa.get("min_inclusivo", True) else ">"
                partes_limite.append(f"{operador} {formatar_numero(minimo, 2)}")
            if maximo is not None:
                operador = "<=" if faixa.get("max_inclusivo", True) else "<"
                partes_limite.append(f"{operador} {formatar_numero(maximo, 2)}")

            unidade = next(
                (
                    regra.unidade for regra in REGRAS
                    if regra.maquina == maquina
                    and regra.parametro == parametro
                ),
                "",
            )
            limites_texto.append(
                f"{parametro}: {' e '.join(partes_limite)} {unidade}".strip()
            )

            if coluna is None:
                dentro_limites[:] = False
                parametros_sem_dados.append(parametro)
                continue

            valores = pd.to_numeric(historico[coluna], errors="coerce")
            valido = valores.notna()

            if minimo is not None:
                if faixa.get("min_inclusivo", True):
                    valido &= valores >= minimo
                else:
                    valido &= valores > minimo

            if maximo is not None:
                if faixa.get("max_inclusivo", True):
                    valido &= valores <= maximo
                else:
                    valido &= valores < maximo

            dentro_limites &= valido

        # A taxa é calculada com a produção incremental e o tempo real entre
        # as leituras, não assumindo que todas as coletas ocorreram a cada 5 s.
        intervalo_horas = (
            historico["data_hora"].diff().dt.total_seconds() / 3600
        )
        producao_intervalo = pd.to_numeric(
            historico.get(
                "producao",
                pd.Series(index=historico.index, dtype="float64"),
            ),
            errors="coerce",
        )
        taxa_hora = producao_intervalo / intervalo_horas

        status_historico = (
            historico["status"].astype(str).str.upper()
            if "status" in historico.columns
            else pd.Series("", index=historico.index)
        )

        intervalos_validos = (
            dentro_limites
            & status_historico.eq("OPERANDO")
            & intervalo_horas.gt(0)
            & taxa_hora.notna()
            & taxa_hora.ge(0)
        )

        taxas = taxa_hora[intervalos_validos]
        p25 = taxas.quantile(0.25) if not taxas.empty else float("nan")
        p90 = taxas.quantile(0.90) if not taxas.empty else float("nan")
        maximo_observado = taxas.max() if not taxas.empty else float("nan")

        resultados.append({
            "Máquina": maquina,
            "Status atual": status_atual,
            "Limites operacionais considerados": (
                "; ".join(limites_texto)
                if limites_texto else "Sem limites cadastrados"
            ),
            "Intervalos válidos": int(len(taxas)),
            "Taxa conservadora (peças/h)": p25,
            "Taxa alta (peças/h)": p90,
            "Maior taxa observada (peças/h)": maximo_observado,
            "Produção estimada conservadora": (
                p25 * duracao_horas if pd.notna(p25) else float("nan")
            ),
            "Produção estimada alta": (
                p90 * duracao_horas if pd.notna(p90) else float("nan")
            ),
            "Parâmetros sem dados": ", ".join(parametros_sem_dados) or "—",
        })

    resultado = pd.DataFrame(resultados)

    if not resultado.empty:
        resultado = resultado.sort_values(
            "Produção estimada alta",
            ascending=False,
            na_position="last",
        ).reset_index(drop=True)
        resultado.insert(0, "Prioridade", range(1, len(resultado) + 1))

    return resultado


# ---------------------------------------------------------------------------
# Página: Análise de médias (antiga página de simulação)
# ---------------------------------------------------------------------------
def pagina_simulacao() -> None:
    cabecalho(
        "Análise de médias",
        "Médias históricas das grandezas em relação às faixas normais de operação.",
        "Análise histórica",
        "ok",
    )

    dados_base = df.copy()
    dados_base["_data_analise"] = pd.to_datetime(
        dados_base["data_hora"],
        errors="coerce",
        utc=True,
    )
    datas_validas = dados_base["_data_analise"].dropna()

    if datas_validas.empty:
        st.warning("Não existem datas válidas no histórico.")
        return

    col_inicio, col_fim = st.columns(2)
    with col_inicio:
        data_inicio = st.date_input(
            "Data inicial",
            value=datas_validas.min().date(),
            key="analise_data_inicio",
        )
    with col_fim:
        data_fim = st.date_input(
            "Data final",
            value=datas_validas.max().date(),
            key="analise_data_fim",
        )

    if data_inicio > data_fim:
        st.warning("A data inicial não pode ser posterior à data final.")
        return

    dados = dados_base[
        dados_base["maquina"].isin(maquinas_selecionadas)
        & (dados_base["_data_analise"].dt.date >= data_inicio)
        & (dados_base["_data_analise"].dt.date <= data_fim)
    ].copy()

    if dados.empty:
        st.info("Não existem leituras para os filtros selecionados.")
        return

    # Simulação emergencial: projeção da produção para todas as máquinas.
    st.divider()
    st.subheader("Previsão de produção em regime emergencial")
    st.write(
        "Projeta quanto cada máquina pode produzir durante um período definido, "
        "usando seu desempenho histórico enquanto operava dentro dos limites "
        "operacionais cadastrados. Todas as máquinas do histórico entram na análise."
    )

    duracao_horas = st.number_input(
        "Por quantas horas a produção emergencial será mantida?",
        min_value=0.25,
        max_value=168.0,
        value=2.0,
        step=0.25,
        key="duracao_previsao_emergencial",
        help="A estimativa é calculada em peças por hora e projetada para esse período.",
    )

    col_gerar, col_limpar = st.columns([1, 5])
    with col_gerar:
        gerar_previsao = st.button(
            "Simular produção emergencial",
            type="primary",
            use_container_width=True,
            key="btn_gerar_previsao_emergencial",
        )
    with col_limpar:
        limpar_previsao = st.button(
            "Limpar previsão",
            use_container_width=True,
            key="btn_limpar_previsao_emergencial",
        )

    if limpar_previsao:
        st.session_state.pop("previsao_emergencial", None)
        st.session_state.pop("duracao_previsao_gerada", None)

    if gerar_previsao:
        # Usa todas as máquinas do período, sem aplicar o multiselect da barra lateral.
        previsao = gerar_previsao_emergencial(
            dados_base[
                (dados_base["_data_analise"].dt.date >= data_inicio)
                & (dados_base["_data_analise"].dt.date <= data_fim)
            ].copy(),
            float(duracao_horas),
        )
        st.session_state["previsao_emergencial"] = previsao
        st.session_state["duracao_previsao_gerada"] = float(duracao_horas)

    if "previsao_emergencial" in st.session_state:
        previsao = st.session_state["previsao_emergencial"]
        duracao_gerada = st.session_state.get(
            "duracao_previsao_gerada", duracao_horas
        )

        if previsao.empty:
            st.warning("Não foi possível gerar uma previsão com os dados disponíveis.")
        else:
            total_conservador = previsao[
                "Produção estimada conservadora"
            ].sum(min_count=1)
            total_alto = previsao[
                "Produção estimada alta"
            ].sum(min_count=1)
            maquinas_com_estimativa = previsao[
                "Taxa alta (peças/h)"
            ].notna().sum()
            maquinas_sem_estimativa = len(previsao) - maquinas_com_estimativa

            st.success(
                f"Simulação gerada para {duracao_gerada:g} hora(s), "
                f"considerando {len(previsao)} máquina(s)."
            )

            c1, c2, c3 = st.columns(3)
            c1.markdown(
                kpi(
                    "Cenário conservador",
                    formatar_numero(total_conservador, 0),
                    f"peças em {duracao_gerada:g} h (P25)",
                    "ok",
                ),
                unsafe_allow_html=True,
            )
            c2.markdown(
                kpi(
                    "Cenário de alto desempenho",
                    formatar_numero(total_alto, 0),
                    f"peças em {duracao_gerada:g} h (P90)",
                    "warn",
                ),
                unsafe_allow_html=True,
            )
            c3.markdown(
                kpi(
                    "Máquinas sem estimativa",
                    formatar_numero(maquinas_sem_estimativa, 0),
                    f"de {len(previsao)} máquinas analisadas",
                    "warn" if maquinas_sem_estimativa else "ok",
                ),
                unsafe_allow_html=True,
            )

            tabela_previsao = previsao.copy()
            colunas_numericas = [
                "Taxa conservadora (peças/h)",
                "Taxa alta (peças/h)",
                "Maior taxa observada (peças/h)",
                "Produção estimada conservadora",
                "Produção estimada alta",
            ]
            for coluna in colunas_numericas:
                tabela_previsao[coluna] = tabela_previsao[coluna].round(2)

            st.markdown("**Previsão por máquina**")
            st.dataframe(
                tabela_previsao,
                use_container_width=True,
                hide_index=True,
            )

            st.download_button(
                "Exportar previsão emergencial (CSV)",
                data=tabela_previsao.to_csv(index=False).encode("utf-8-sig"),
                file_name="previsao_producao_emergencial.csv",
                mime="text/csv",
                key="download_previsao_emergencial",
            )

            sem_taxa = tabela_previsao[
                tabela_previsao["Taxa alta (peças/h)"].isna()
            ]
            if not sem_taxa.empty:
                with st.expander("Máquinas sem dados suficientes para estimar"):
                    st.dataframe(
                        sem_taxa[
                            [
                                "Máquina",
                                "Status atual",
                                "Intervalos válidos",
                                "Parâmetros sem dados",
                                "Limites operacionais considerados",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

            st.caption(
                "P25 representa um cenário conservador (percentil 25) e P90 "
                "um cenário de alto desempenho (percentil 90) das taxas reais "
                "de produção por hora observadas com a máquina OPERANDO e "
                "dentro das faixas cadastradas. A simulação inclui todas as "
                "máquinas, mas máquinas sem intervalos históricos válidos "
                "aparecem sem estimativa."
            )
            st.warning(
                "Esta é uma projeção estatística baseada no histórico, não "
                "uma garantia de capacidade nem uma simulação física de "
                "aceleração. Para prever quanto a produção aumenta ao aproximar "
                "cada sensor do limite, é necessário conhecer/modelar a relação "
                "entre cada indicador e a velocidade de produção."
            )

    st.divider()

    resultados = {
        "Abaixo do limite": [],
        "Acima do limite": [],
        "Dentro dos limites": [],
    }

    for (maquina, parametro), faixa in FAIXAS_NORMAIS.items():
        if maquina not in maquinas_selecionadas:
            continue

        dados_maquina = dados[dados["maquina"] == maquina]
        if dados_maquina.empty:
            continue

        aliases = ALIASES.get(parametro, (parametro,))
        coluna = next(
            (
                c for c in aliases
                if c in dados.columns
                and pd.to_numeric(
                    dados_maquina[c],
                    errors="coerce",
                ).notna().any()
            ),
            None,
        )
        if coluna is None:
            continue

        leituras = pd.to_numeric(
            dados_maquina[coluna],
            errors="coerce",
        ).dropna()
        if leituras.empty:
            continue

        abaixo = pd.Series(False, index=leituras.index)
        acima = pd.Series(False, index=leituras.index)

        minimo = faixa["min"]
        maximo = faixa["max"]

        if minimo is not None:
            abaixo = (
                leituras.lt(minimo)
                if faixa["min_inclusivo"]
                else leituras.le(minimo)
            )

        if maximo is not None:
            acima = (
                leituras.gt(maximo)
                if faixa["max_inclusivo"]
                else leituras.ge(maximo)
            )

        dentro = ~(abaixo | acima)
        cenarios = {
            "Abaixo do limite": leituras[abaixo],
            "Acima do limite": leituras[acima],
            "Dentro dos limites": leituras[dentro],
        }

        producao_intervalo = pd.to_numeric(
            dados_maquina["producao"],
            errors="coerce",
        )

        unidade = next(
            (
                regra.unidade
                for regra in REGRAS
                if regra.maquina == maquina
                and regra.parametro == parametro
            ),
            "",
        )

        for nome, valores in cenarios.items():
            if valores.empty:
                continue

            producao_cenario = producao_intervalo.reindex(
                valores.index
            ).dropna()

            resultados[nome].append({
                "Máquina": maquina,
                "Grandeza": parametro.capitalize(),
                "Unidade": unidade,
                "Quantidade de leituras": len(valores),
                "Média da grandeza": valores.mean(),
                "Média produzida no intervalo": (
                    producao_cenario.mean()
                    if not producao_cenario.empty
                    else None
                ),
            })

    for nome in (
        "Abaixo do limite",
        "Acima do limite",
        "Dentro dos limites",
    ):
        secao(nome)
        tabela = pd.DataFrame(resultados[nome])

        if tabela.empty:
            st.info("Nenhuma leitura encontrada neste cenário.")
            continue

        tabela["Média da grandeza"] = tabela[
            "Média da grandeza"
        ].round(2)
        tabela["Média produzida no intervalo"] = tabela[
            "Média produzida no intervalo"
        ].round(2)

        st.dataframe(
            tabela,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            f"Exportar {nome.lower()}",
            data=tabela.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{nome.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            key=f"exportar_{nome}",
        )


# ---------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------
if st.session_state.pagina == "criticos":
    pagina_criticos()
elif st.session_state.pagina == "simulacao":
    pagina_simulacao()
else:
    pagina_geral()

st.markdown(
    f'<div class="rodape">Banco de dados: MySQL – Clever Cloud  ·  '
    f'Última atualização da página: '
    f'{pd.Timestamp.now().strftime("%d/%m/%Y %H:%M:%S")}</div>',
    unsafe_allow_html=True,
)
