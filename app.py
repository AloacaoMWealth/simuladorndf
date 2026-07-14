from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


st.set_page_config(
    page_title="Simulador de NDF | Trava Cambial",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# VISUAL
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
        :root {
            --bg: #f6f8fb;
            --surface: #ffffff;
            --border: #dce5ef;
            --text: #0f2742;
            --muted: #72839a;
            --primary: #0f2742;
            --gold: #c99a2e;
            --soft-blue: #eef4fa;
            --shadow: 0 7px 22px rgba(15, 39, 66, 0.07);
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: var(--bg) !important;
            color: var(--text) !important;
        }

        [data-testid="stHeader"] {
            background: rgba(246, 248, 251, 0.94) !important;
        }

        [data-testid="stSidebar"] {
            background: #ffffff !important;
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: var(--text) !important;
        }

        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 2rem;
            max-width: 1480px;
        }

        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        .stDateInput > div > div,
        .stTextInput > div > div,
        .stNumberInput > div > div {
            background: #ffffff !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            box-shadow: none !important;
        }

        label {
            color: var(--text) !important;
            font-weight: 700 !important;
        }

        .title-wrap {
            border-top: 5px solid var(--primary);
            padding: 18px 4px 12px 4px;
            margin-bottom: 8px;
        }

        .main-title {
            font-family: Georgia, 'Times New Roman', serif;
            color: var(--text);
            font-size: 2.25rem;
            line-height: 1.05;
            margin: 0;
        }

        .subtitle {
            color: var(--muted);
            font-size: 0.98rem;
            margin-top: 8px;
        }

        .panel {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: var(--shadow);
            padding: 20px 22px;
            margin-top: 12px;
        }

        .section-label {
            color: #6e82a0;
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-weight: 800;
            margin-bottom: 4px;
        }

        .section-value {
            color: var(--text);
            font-size: 1.18rem;
            font-weight: 800;
        }

        .gold-value {
            color: var(--gold);
        }

        .muted-small {
            color: var(--muted);
            font-size: 0.80rem;
            margin-top: 4px;
        }

        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 15px;
            box-shadow: var(--shadow);
        }

        [data-testid="stMetricLabel"] {
            color: var(--muted) !important;
            font-size: 0.78rem;
            font-weight: 700;
        }

        [data-testid="stMetricValue"] {
            color: var(--text) !important;
            font-size: 1.45rem;
            font-weight: 800;
        }

        .stAlert {
            border-radius: 12px;
            border: 1px solid var(--border);
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }

        .footer-note {
            color: var(--muted);
            font-size: 0.78rem;
            line-height: 1.45;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# FORMATOS E CÁLCULOS
# -----------------------------------------------------------------------------
def parse_br_number(value: str) -> float:
    text = str(value).strip().replace("R$", "").replace("US$", "").replace("%", "").strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    return float(text)


def fmt_number(value: float, decimals: int = 4) -> str:
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_brl(value: float, decimals: int = 0) -> str:
    return f"R$ {fmt_number(value, decimals)}"


def fmt_usd(value: float, decimals: int = 0) -> str:
    return f"USD {fmt_number(value, decimals)}"


def fmt_pct(value: float, decimals: int = 2) -> str:
    return f"{fmt_number(value * 100, decimals)}%"


def business_days(start: date, end: date) -> int:
    if end <= start:
        return 0
    return int(np.busday_count(start.isoformat(), end.isoformat()))


def indicative_forward_linear(
    spot: float,
    rate_usd: float,
    rate_brl: float,
    days: int,
    basis: int = 360,
) -> float:
    """Taxa a termo meramente indicativa, por juros simples Dias/360."""
    usd_factor = 1 + rate_usd * days / basis
    brl_factor = 1 + rate_brl * days / basis
    return spot * brl_factor / usd_factor


def ndf_result(
    fixing: float,
    contracted_rate: float,
    notional_usd: float,
    operation: str,
) -> float:
    gross = (fixing - contracted_rate) * notional_usd
    return gross if operation == "Compra" else -gross


# -----------------------------------------------------------------------------
# PTAX BCB
# -----------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_latest_ptax(lookback_days: int = 15) -> dict:
    """
    Busca a última PTAX disponível no serviço OData do Banco Central.
    Prioriza o boletim 'Fechamento PTAX'. Caso não exista, usa o registro mais recente.
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)

    endpoint = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    )
    params = {
        "@dataInicial": f"'{start.strftime('%m-%d-%Y')}'",
        "@dataFinalCotacao": f"'{end.strftime('%m-%d-%Y')}'",
        "$format": "json",
        "$top": "500",
    }

    response = requests.get(endpoint, params=params, timeout=12)
    response.raise_for_status()
    values = response.json().get("value", [])

    if not values:
        raise RuntimeError("Nenhuma cotação PTAX foi retornada pelo Banco Central.")

    def parse_dt(item: dict) -> datetime:
        raw = str(item.get("dataHoraCotacao", ""))
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))

    closing = [
        item for item in values
        if "fechamento" in str(item.get("tipoBoletim", "")).lower()
    ]
    pool = closing if closing else values
    latest = max(pool, key=parse_dt)

    buy = float(latest["cotacaoCompra"])
    sell = float(latest["cotacaoVenda"])

    return {
        "buy": buy,
        "sell": sell,
        "mid": (buy + sell) / 2,
        "datetime": parse_dt(latest),
        "bulletin": latest.get("tipoBoletim", "Não informado"),
        "source": "Banco Central do Brasil - PTAX",
    }


ptax_data = None
ptax_error = None
try:
    ptax_data = fetch_latest_ptax()
except Exception as exc:
    ptax_error = str(exc)


# -----------------------------------------------------------------------------
# CABEÇALHO
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="title-wrap">
        <div class="main-title">Simulador de NDF / Trava Cambial</div>
        <div class="subtitle">Simulação indicativa de compra ou venda de moeda, resultado no vencimento e proteção cambial.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# INPUTS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Configuração")

    operation = st.radio("Operação", ["Compra", "Venda"], horizontal=True)
    operation_note = "Importação / compra futura de moeda" if operation == "Compra" else "Exportação / venda futura de moeda"
    st.caption(operation_note)

    notional_text = st.text_input("Volume em USD", value="1.000.000,00")
    maturity = st.date_input(
        "Data de vencimento",
        value=date.today() + timedelta(days=360),
        min_value=date.today() + timedelta(days=1),
        format="DD/MM/YYYY",
    )

    st.divider()
    st.markdown("### Spot de referência")

    ptax_choice = st.selectbox(
        "Critério da PTAX",
        ["Média entre compra e venda", "Cotação de venda", "Cotação de compra", "Manual"],
    )

    if ptax_data and ptax_choice != "Manual":
        automatic_spot = {
            "Média entre compra e venda": ptax_data["mid"],
            "Cotação de venda": ptax_data["sell"],
            "Cotação de compra": ptax_data["buy"],
        }[ptax_choice]
        spot_text = st.text_input("USD/BRL", value=fmt_number(automatic_spot, 4))
        st.caption(
            f"{ptax_data['bulletin']} - {ptax_data['datetime'].strftime('%d/%m/%Y %H:%M')}"
        )
    else:
        spot_text = st.text_input("USD/BRL", value="5,0725")
        if ptax_error:
            st.warning("PTAX automática indisponível. O valor pode ser preenchido manualmente.")

    st.divider()
    st.markdown("### Taxa do NDF")

    rate_mode = st.radio(
        "Origem da taxa",
        ["Taxa negociada / manual", "Over sobre o spot", "Taxa a termo indicativa"],
    )

    manual_ndf_text = None
    over_text = None
    usd_rate_text = None
    brl_rate_text = None

    if rate_mode == "Taxa negociada / manual":
        manual_ndf_text = st.text_input("Taxa NDF contratada", value=spot_text)
        st.caption("Utilize a cotação efetivamente oferecida ou contratada pela contraparte.")

    elif rate_mode == "Over sobre o spot":
        over_text = st.text_input("Over spot (%)", value="0,00")
        st.caption("A taxa NDF será calculada como Spot × (1 + Over).")

    else:
        usd_rate_text = st.text_input("Juros USD (% a.a.)", value="3,75")
        brl_rate_text = st.text_input("Juros BRL (% a.a.)", value="14,25")
        st.caption("Referência didática por juros simples Dias/360. Não equivale, por si só, a uma cotação executável de mesa.")


try:
    notional = parse_br_number(notional_text)
    spot = parse_br_number(spot_text)

    if notional <= 0 or spot <= 0:
        raise ValueError
except Exception:
    st.error("Revise o volume e o spot. Use valores positivos no padrão brasileiro.")
    st.stop()

calendar_days = (maturity - date.today()).days
useful_days = business_days(date.today(), maturity)

try:
    if rate_mode == "Taxa negociada / manual":
        ndf_rate = parse_br_number(manual_ndf_text)
        calculation_note = "Taxa informada manualmente pelo usuário."

    elif rate_mode == "Over sobre o spot":
        entered_over = parse_br_number(over_text) / 100
        ndf_rate = spot * (1 + entered_over)
        calculation_note = f"Taxa = Spot × (1 + {fmt_pct(entered_over)})."

    else:
        usd_rate = parse_br_number(usd_rate_text) / 100
        brl_rate = parse_br_number(brl_rate_text) / 100
        ndf_rate = indicative_forward_linear(spot, usd_rate, brl_rate, calendar_days)
        calculation_note = "Taxa indicativa por diferencial de juros simples Dias/360."

    if ndf_rate <= 0:
        raise ValueError
except Exception:
    st.error("Revise os parâmetros utilizados para calcular a taxa NDF.")
    st.stop()

over_spot = ndf_rate / spot - 1
notional_brl_spot = spot * notional
notional_brl_locked = ndf_rate * notional


# -----------------------------------------------------------------------------
# PAINEL PRINCIPAL
# -----------------------------------------------------------------------------
st.markdown('<div class="panel">', unsafe_allow_html=True)
input_c1, input_c2, input_c3 = st.columns([1, 1, 1])

with input_c1:
    st.markdown('<div class="section-label">Operação</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">{operation}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="muted-small">{operation_note}</div>', unsafe_allow_html=True)

with input_c2:
    st.markdown('<div class="section-label">Spot referência</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">USD/BRL &nbsp; {fmt_number(spot, 4)}</div>', unsafe_allow_html=True)
    if ptax_data:
        st.markdown(
            f'<div class="muted-small">PTAX disponível em {ptax_data["datetime"].strftime("%d/%m/%Y")}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="muted-small">Valor informado manualmente</div>', unsafe_allow_html=True)

with input_c3:
    st.markdown('<div class="section-label">Volume</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">{fmt_usd(notional, 2)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="muted-small">≈ {fmt_brl(notional_brl_spot, 2)}</div>', unsafe_allow_html=True)

st.divider()

summary_1, summary_2, summary_3, summary_4, summary_5 = st.columns([1.15, 1, 1, 1, 1.25])

with summary_1:
    st.markdown('<div class="section-label">Vencimento</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">{maturity.strftime("%d/%m/%Y")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="muted-small">{useful_days} DU / {calendar_days} DC</div>', unsafe_allow_html=True)

with summary_2:
    st.markdown('<div class="section-label">Taxa NDF</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value gold-value">{fmt_number(ndf_rate, 4)}</div>', unsafe_allow_html=True)

with summary_3:
    st.markdown('<div class="section-label">Over spot</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value gold-value">{fmt_pct(over_spot)}</div>', unsafe_allow_html=True)

with summary_4:
    st.markdown('<div class="section-label">Volume USD</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">{fmt_usd(notional, 2)}</div>', unsafe_allow_html=True)

with summary_5:
    st.markdown('<div class="section-label">Equivalente BRL</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-value">{fmt_brl(notional_brl_locked, 2)}</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# RESULTADO E PAYOFF
# -----------------------------------------------------------------------------
st.markdown('<div class="panel">', unsafe_allow_html=True)
header_left, header_right = st.columns([4, 1])
with header_left:
    st.markdown(
        f"**{operation.upper()} - {'IMPORTAÇÃO' if operation == 'Compra' else 'EXPORTAÇÃO'}**"
    )
with header_right:
    st.markdown("**NDF**")

fixing_default = ndf_rate * (1.05 if operation == "Compra" else 0.95)
fixing_text = st.text_input(
    "Simular USD/BRL no vencimento",
    value=fmt_number(fixing_default, 4),
    help="Cotação de referência utilizada para calcular o resultado financeiro do NDF no vencimento.",
)

try:
    fixing = parse_br_number(fixing_text)
    if fixing <= 0:
        raise ValueError
except Exception:
    st.error("Informe uma cotação válida para o vencimento.")
    st.stop()

result_brl = ndf_result(fixing, ndf_rate, notional, operation)
open_value = fixing * notional
hedged_value = ndf_rate * notional

result_c1, result_c2, result_c3, result_c4 = st.columns(4)
result_c1.metric("Dólar travado", fmt_number(ndf_rate, 4))
result_c2.metric("USD/BRL no vencimento", fmt_number(fixing, 4))
result_c3.metric("Resultado financeiro do NDF", fmt_brl(result_brl, 0))
result_c4.metric(
    "Custo / receita protegida",
    fmt_brl(hedged_value, 0),
    delta=fmt_brl(hedged_value - open_value, 0),
    delta_color="off",
)

x_min = max(0.01, ndf_rate * 0.78)
x_max = ndf_rate * 1.22
x_values = np.linspace(x_min, x_max, 101)
y_values = [ndf_result(x, ndf_rate, notional, operation) for x in x_values]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=x_values,
        y=y_values,
        mode="lines",
        name="NDF",
        line=dict(color="#0f2742", width=3),
        hovertemplate="USD/BRL: %{x:.4f}<br>Resultado: R$ %{y:,.0f}<extra></extra>",
    )
)
fig.add_hline(y=0, line_color="#aebdce", line_width=1)
fig.add_vline(x=ndf_rate, line_color="#c99a2e", line_dash="dot", line_width=1.5)
fig.add_trace(
    go.Scatter(
        x=[fixing],
        y=[result_brl],
        mode="markers",
        name="Cenário",
        marker=dict(size=10, color="#c99a2e"),
        hovertemplate="Cenário: %{x:.4f}<br>Resultado: R$ %{y:,.0f}<extra></extra>",
    )
)
fig.update_layout(
    template="plotly_white",
    height=430,
    margin=dict(l=20, r=20, t=20, b=20),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#ffffff",
    xaxis_title="USD/BRL no vencimento",
    yaxis_title="Resultado financeiro em R$",
    hovermode="x unified",
    showlegend=False,
    font=dict(color="#0f2742"),
)
fig.update_xaxes(showgrid=True, gridcolor="#e8eef5", zeroline=False)
fig.update_yaxes(showgrid=True, gridcolor="#e8eef5", zeroline=False)
st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
def build_pdf() -> bytes:
    chart_buffer = BytesIO()
    pdf_buffer = BytesIO()

    plt.figure(figsize=(10.5, 4.0))
    plt.plot(x_values, y_values, linewidth=2.2)
    plt.axhline(0, linewidth=0.8)
    plt.axvline(ndf_rate, linewidth=0.8, linestyle="--")
    plt.scatter([fixing], [result_brl], s=35)
    plt.xlabel("USD/BRL no vencimento")
    plt.ylabel("Resultado financeiro em R$")
    plt.grid(alpha=0.20)
    plt.tight_layout()
    plt.savefig(chart_buffer, format="png", dpi=160, bbox_inches="tight")
    plt.close()
    chart_buffer.seek(0)

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#0f2742"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "CustomSub",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#72839a"),
        alignment=TA_LEFT,
    )

    story = [
        Paragraph("Simulação de NDF / Trava Cambial", title_style),
        Paragraph(
            f"Non-Deliverable Forward - {operation} - {'Importação' if operation == 'Compra' else 'Exportação'}",
            subtitle_style,
        ),
        Spacer(1, 7 * mm),
    ]

    operation_data = [
        ["Operação", operation, "Volume", fmt_usd(notional, 2)],
        ["Spot de referência", fmt_number(spot, 4), "Taxa NDF", fmt_number(ndf_rate, 4)],
        ["Vencimento", maturity.strftime("%d/%m/%Y"), "Prazo", f"{useful_days} DU / {calendar_days} DC"],
        ["Over spot", fmt_pct(over_spot), "Equivalente BRL", fmt_brl(notional_brl_locked, 2)],
        ["USD/BRL no vencimento", fmt_number(fixing, 4), "Resultado do NDF", fmt_brl(result_brl, 2)],
    ]

    operation_table = Table(operation_data, colWidths=[42 * mm, 48 * mm, 42 * mm, 55 * mm])
    operation_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f2742")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce5ef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    story.extend(
        [
            operation_table,
            Spacer(1, 6 * mm),
            Image(chart_buffer, width=245 * mm, height=92 * mm),
            Spacer(1, 3 * mm),
            Paragraph(
                "Simulação meramente indicativa. A liquidação efetiva depende da taxa de referência, das condições contratuais e da contraparte.",
                subtitle_style,
            ),
        ]
    )

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.read()


pdf_bytes = build_pdf()
st.download_button(
    "Gerar PDF da simulação",
    data=pdf_bytes,
    file_name=f"simulacao_ndf_{maturity.strftime('%Y%m%d')}.pdf",
    mime="application/pdf",
    use_container_width=False,
)


# -----------------------------------------------------------------------------
# DETALHES TÉCNICOS
# -----------------------------------------------------------------------------
with st.expander("Metodologia, PTAX e memória de cálculo"):
    details = pd.DataFrame(
        {
            "Item": [
                "Operação",
                "Spot de referência",
                "Origem da taxa NDF",
                "Taxa NDF",
                "Over spot",
                "Dias corridos",
                "Dias úteis estimados",
                "Resultado no cenário",
            ],
            "Valor": [
                operation,
                fmt_number(spot, 4),
                rate_mode,
                fmt_number(ndf_rate, 4),
                fmt_pct(over_spot),
                str(calendar_days),
                str(useful_days),
                fmt_brl(result_brl, 2),
            ],
        }
    )
    st.dataframe(details, hide_index=True, use_container_width=True)

    st.markdown(f"**Memória da taxa:** {calculation_note}")

    if ptax_data:
        st.markdown(
            f"**PTAX utilizada como referência:** compra {fmt_number(ptax_data['buy'], 4)}, "
            f"venda {fmt_number(ptax_data['sell'], 4)}, boletim {ptax_data['bulletin']}, "
            f"publicado em {ptax_data['datetime'].strftime('%d/%m/%Y %H:%M')}."
        )
    else:
        st.markdown("**PTAX:** consulta automática indisponível nesta execução; foi permitido o preenchimento manual.")

    st.info(
        "A PTAX é apenas a referência inicial desta simulação. O contrato deve definir a taxa de fixing utilizada na liquidação. "
        "A taxa a termo indicativa por juros simples não deve ser tratada automaticamente como uma cotação executável de NDF."
    )

st.markdown(
    """
    <div class="footer-note">
        Ferramenta para simulação indicativa. Não constitui recomendação, oferta, confirmação de preço ou compromisso de execução.
        Dias úteis consideram apenas segunda a sexta nesta versão; feriados e convenções contratuais devem ser validados.
    </div>
    """,
    unsafe_allow_html=True,
)
