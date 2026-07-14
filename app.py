from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Simulador NDF | Validado",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --bg: #f6f8fc;
            --surface: #ffffff;
            --border: #dce5f2;
            --text: #12233d;
            --muted: #66758c;
            --primary: #1d4ed8;
            --primary-soft: #ecf3ff;
            --shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }
        html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
            background: var(--bg) !important;
            color: var(--text) !important;
        }
        [data-testid="stHeader"] { background: rgba(246, 248, 252, .94) !important; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 1500px; }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f7fbff 100%) !important;
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] * { color: var(--text) !important; }
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        .stDateInput > div > div,
        .stTextInput > div > div,
        .stNumberInput > div > div {
            border-radius: 12px !important;
            border: 1px solid var(--border) !important;
            background: #ffffff !important;
            box-shadow: none !important;
        }
        label { font-weight: 600 !important; color: var(--text) !important; }
        .hero-card {
            background: linear-gradient(135deg, #ffffff 0%, #f2f7ff 100%);
            border: 1px solid #dce8ff;
            border-radius: 22px;
            padding: 24px 26px 18px 26px;
            box-shadow: var(--shadow);
            margin-bottom: 14px;
        }
        .hero-title {
            font-size: 2.05rem;
            font-weight: 800;
            color: var(--text);
            line-height: 1.1;
            margin: 0;
        }
        .hero-subtitle {
            color: var(--muted);
            margin-top: 8px;
            margin-bottom: 14px;
            font-size: .98rem;
        }
        .hero-chip-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .hero-chip {
            background: var(--primary-soft);
            color: var(--primary);
            border: 1px solid #d5e4ff;
            border-radius: 999px;
            padding: 8px 12px;
            font-size: .88rem;
            font-weight: 700;
        }
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 16px;
            box-shadow: var(--shadow);
        }
        [data-testid="stMetricLabel"] { color: var(--muted) !important; font-weight: 700; }
        [data-testid="stMetricValue"] { color: var(--text) !important; font-weight: 800; }
        .section-title {
            font-size: 1.30rem;
            font-weight: 800;
            color: var(--text);
            margin: 18px 0 10px 0;
        }
        .section-subtitle {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text);
            margin: 6px 0 10px 0;
        }
        [data-testid="stDataFrame"] {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 18px;
            box-shadow: var(--shadow);
            overflow: hidden;
        }
        .stAlert {
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }
        .small-box {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px;
            box-shadow: var(--shadow);
        }
        .small-note {
            font-size: .91rem;
            color: var(--muted);
            line-height: 1.55;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

px.defaults.template = "plotly_white"


def parse_decimal(value: str) -> float:
    txt = str(value).strip().replace(".", "").replace(",", ".") if "," in str(value) else str(value).strip()
    return float(txt)


def dec4(value: float) -> str:
    return f"{value:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")


def dec2(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def money_brl(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def money_usd(value: float, decimals: int = 0) -> str:
    formatted = f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {formatted}"


def pct(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def linear_forward(spot: float, base_rate: float, quote_rate: float, days: int, basis: int = 360) -> tuple[float, float, float, float]:
    base_factor = 1 + base_rate * days / basis
    quote_factor = 1 + quote_rate * days / basis
    forward = spot * quote_factor / base_factor
    return forward, base_factor, quote_factor, forward - spot


def ndf_pnl(settlement_fx: float, contracted_fx: float, notional_usd: float, direction: str) -> float:
    base = (settlement_fx - contracted_fx) * notional_usd
    return base if direction == "Compra de USD" else -base


def chart_style(fig, y_title: str):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#12233d"),
        title_font=dict(size=18),
        hovermode="x unified",
        xaxis_title="PTAX / BRL por USD",
        yaxis_title=y_title,
        margin=dict(l=20, r=20, t=60, b=20),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#e7edf5", zeroline=False)
    return fig


DEFAULT_START = date(2026, 7, 14)
DEFAULT_END = date(2027, 7, 9)

with st.sidebar:
    st.markdown("## Parâmetros")
    st.caption("Estrutura simplificada e alinhada com a calculadora de taxa a termo.")

    pair = st.selectbox("Par de moedas", ["USD/BRL", "BRL/USD"], index=0)
    direction = st.selectbox("Tipo de proteção", ["Compra de USD", "Venda de USD"], index=0)
    notional = st.number_input("Nocional em USD", min_value=1_000.0, value=1_000_000.0, step=50_000.0, format="%.2f")

    st.divider()

    if pair == "USD/BRL":
        default_spot = "5,0725"
        default_base = "3,75"
        default_quote = "14,25"
        base_ccy = "USD"
        quote_ccy = "BRL"
    else:
        default_spot = "0,1971"
        default_base = "14,25"
        default_quote = "3,75"
        base_ccy = "BRL"
        quote_ccy = "USD"

    spot_str = st.text_input("Preço à vista", value=default_spot)
    base_rate_str = st.text_input(f"Juros da moeda base ({base_ccy}) % a.a.", value=default_base)
    quote_rate_str = st.text_input(f"Juros da moeda cotada ({quote_ccy}) % a.a.", value=default_quote)

    settlement_date = st.date_input("Data de liquidação", value=DEFAULT_START, format="DD/MM/YYYY")
    forward_date = st.date_input("Data da taxa a termo", value=DEFAULT_END, format="DD/MM/YYYY")

    days = (forward_date - settlement_date).days
    st.text_input("Dias", value=str(days), disabled=True)
    basis_label = st.selectbox("Base", ["Dias/360"], index=0)
    basis = 360

    st.divider()
    spread_str = st.text_input("Spread do banco em pontos (BRL/USD)", value="0,0300")
    use_manual_contract = st.checkbox("Informar taxa contratada manualmente")
    manual_contract_str = st.text_input("Taxa contratada (BRL/USD)", value="5,6159", disabled=not use_manual_contract)

try:
    spot = parse_decimal(spot_str)
    base_rate = parse_decimal(base_rate_str) / 100
    quote_rate = parse_decimal(quote_rate_str) / 100
    spread_points = parse_decimal(spread_str)
    manual_contract = parse_decimal(manual_contract_str) if use_manual_contract else None
except Exception:
    st.error("Revise os campos numéricos. Use formatos como 5,0725 ou 14,25.")
    st.stop()

if days <= 0:
    st.error("A data da taxa a termo precisa ser posterior à data de liquidação.")
    st.stop()

forward_rate_pair, base_factor, quote_factor, term_points_pair = linear_forward(
    spot=spot,
    base_rate=base_rate,
    quote_rate=quote_rate,
    days=days,
    basis=basis,
)

pips = term_points_pair * 10000

# Taxa operacional BRL/USD para o hedge
if pair == "USD/BRL":
    fair_forward_brlusd = forward_rate_pair
    spot_brlusd = spot
else:
    fair_forward_brlusd = 1 / forward_rate_pair
    spot_brlusd = 1 / spot

quoted_forward_brlusd = fair_forward_brlusd + spread_points if direction == "Compra de USD" else fair_forward_brlusd - spread_points
contracted_forward_brlusd = manual_contract if manual_contract is not None else quoted_forward_brlusd
implied_spread_brl = abs(contracted_forward_brlusd - fair_forward_brlusd) * notional
protected_value_brl = contracted_forward_brlusd * notional

st.markdown(
    f"""
    <div class="hero-card">
        <div class="hero-title">Simulador de NDF e Hedge Cambial</div>
        <div class="hero-chip-wrap">
            <div class="hero-chip">{pair}</div>
            <div class="hero-chip">{direction}</div>
            <div class="hero-chip">Nocional: {money_usd(notional, 0)}</div>
            <div class="hero-chip">Dias: {days}</div>
            <div class="hero-chip">Base: {basis_label}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Preço à vista", dec4(spot))
m2.metric("Taxa a termo", dec4(forward_rate_pair))
m3.metric("Termo em pontos", dec4(term_points_pair))
m4.metric("Pips", dec2(pips))
m5.metric("Valor protegido", money_brl(protected_value_brl, 0))

st.markdown('<div class="section-title">Resultado da operação</div>', unsafe_allow_html=True)
col_left, col_right = st.columns([1, 1.6])

with col_left:
    st.markdown('<div class="small-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">Cenário de liquidação</div>', unsafe_allow_html=True)
    settlement_fx = st.text_input("PTAX simulada (BRL/USD)", value=dec4(contracted_forward_brlusd * 1.03), key="settle")
    try:
        settlement_fx_val = parse_decimal(settlement_fx)
    except Exception:
        st.error("PTAX simulada inválida.")
        st.stop()

    pnl = ndf_pnl(settlement_fx_val, contracted_forward_brlusd, notional, direction)
    unhedged_value = settlement_fx_val * notional
    hedged_value = contracted_forward_brlusd * notional
    effective_value = unhedged_value - pnl if direction == "Compra de USD" else unhedged_value + pnl

    a1, a2 = st.columns(2)
    a1.metric("Taxa considerada", dec4(contracted_forward_brlusd))
    a2.metric("Resultado do NDF", money_brl(pnl, 0))

    b1, b2 = st.columns(2)
    b1.metric("Sem hedge", money_brl(unhedged_value, 0))
    b2.metric("Com hedge", money_brl(effective_value, 0))

    st.caption(
        "Compra de USD: o derivativo compensa a alta do câmbio. Venda de USD: o derivativo protege a receita em reais."
    )
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    low = max(0.10, contracted_forward_brlusd * 0.85)
    high = contracted_forward_brlusd * 1.15
    fx_range = np.linspace(low, high, 61)
    without_hedge = fx_range * notional
    with_hedge = np.full_like(fx_range, contracted_forward_brlusd * notional)

    chart_df = pd.DataFrame(
        {
            "PTAX / BRL por USD": np.tile(fx_range, 2),
            "Valor em R$": np.concatenate([without_hedge, with_hedge]),
            "Estratégia": ["Sem hedge"] * len(fx_range) + ["Com NDF"] * len(fx_range),
        }
    )

    graph_title = "Custo da obrigação com e sem hedge" if direction == "Compra de USD" else "Receita do recebimento com e sem hedge"
    fig = px.line(chart_df, x="PTAX / BRL por USD", y="Valor em R$", color="Estratégia", title=graph_title)
    chart_style(fig, "Valor total em R$")
    st.plotly_chart(fig, use_container_width=True)

st.markdown('<div class="section-title">Resumo rápido</div>', unsafe_allow_html=True)
summary_df = pd.DataFrame(
    {
        "Campo": [
            "Par de moedas",
            "Data de liquidação",
            "Data da taxa a termo",
            "Preço à vista",
            f"Juros moeda base ({base_ccy})",
            f"Juros moeda cotada ({quote_ccy})",
            "Taxa a termo",
            "Termo em pontos",
            "Pips",
            "Taxa operacional para hedge (BRL/USD)",
        ],
        "Valor": [
            pair,
            settlement_date.strftime("%d/%m/%Y"),
            forward_date.strftime("%d/%m/%Y"),
            dec4(spot),
            pct(base_rate * 100),
            pct(quote_rate * 100),
            dec6 := f"{forward_rate_pair:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            dec6p := f"{term_points_pair:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
            dec2(pips),
            dec4(contracted_forward_brlusd),
        ],
    }
)
st.dataframe(summary_df, hide_index=True, use_container_width=True)

with st.expander("Memória de cálculo e validação"):
    validation_text = (
        "Com os inputs do seu print — USD/BRL, spot 5,0725, juros base 3,75%, juros cotada 14,25% e 360 dias — "
        "a fórmula abaixo gera taxa a termo de 5,585861, termo em pontos de 0,513361 e pips de 5.133,61."
    )
    st.info(validation_text)

    calc_df = pd.DataFrame(
        {
            "Etapa": [
                "Base de cálculo",
                "Fator da moeda base",
                "Fator da moeda cotada",
                "Fórmula da taxa a termo",
                "Termo em pontos",
                "Pips",
                "Observação do hedge",
            ],
            "Valor": [
                f"Juros simples, {days}/{basis}",
                f"1 + {base_rate:.6f} × {days}/{basis} = {base_factor:.8f}",
                f"1 + {quote_rate:.6f} × {days}/{basis} = {quote_factor:.8f}",
                f"{dec4(spot)} × ({quote_factor:.8f} / {base_factor:.8f}) = {forward_rate_pair:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
                f"{term_points_pair:,.6f}".replace(",", "X").replace(".", ",").replace("X", "."),
                dec2(pips),
                "Para o bloco de hedge, a operação é convertida e analisada em BRL/USD.",
            ],
        }
    )
    st.dataframe(calc_df, hide_index=True, use_container_width=True)

st.caption(
    "Ferramenta indicativa. A precificação desta versão segue a convenção linear simples Dias/360 para aderir à calculadora de referência enviada."
)
