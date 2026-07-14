from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Simulador NDF | Hedge Cambial",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --bg: #f5f7fb;
            --surface: #ffffff;
            --surface-2: #f9fbff;
            --border: #dfe7f3;
            --text: #132238;
            --muted: #6b7a90;
            --primary: #1d4ed8;
            --primary-soft: #e8f0ff;
            --success-soft: #edfdf3;
            --shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {
            background: var(--bg) !important;
            color: var(--text) !important;
        }

        [data-testid="stHeader"] {
            background: rgba(245, 247, 251, 0.92) !important;
        }

        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2rem;
            max-width: 1500px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%) !important;
            border-right: 1px solid var(--border);
        }

        [data-testid="stSidebar"] * {
            color: var(--text) !important;
        }

        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="select"],
        [data-testid="stSidebar"] [data-baseweb="popover"],
        [data-testid="stSidebar"] .stDateInput > div,
        [data-testid="stSidebar"] .stNumberInput > div {
            background: #ffffff !important;
        }

        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        .stDateInput > div > div,
        .stNumberInput > div > div,
        .stTextInput > div > div {
            border-radius: 12px !important;
            border: 1px solid var(--border) !important;
            background: #ffffff !important;
            box-shadow: none !important;
        }

        label, .stRadio label, .stSelectbox label, .stDateInput label, .stNumberInput label {
            color: var(--text) !important;
            font-weight: 600 !important;
        }

        .hero-card {
            background: linear-gradient(135deg, #ffffff 0%, #f1f7ff 100%);
            border: 1px solid #d9e7ff;
            border-radius: 22px;
            padding: 24px 26px 18px 26px;
            margin-bottom: 10px;
            box-shadow: var(--shadow);
        }

        .hero-title {
            font-size: 2.15rem;
            line-height: 1.1;
            font-weight: 800;
            color: var(--text);
            margin: 0;
        }

        .hero-subtitle {
            font-size: 0.98rem;
            color: var(--muted);
            margin-top: 8px;
            margin-bottom: 16px;
        }

        .hero-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .hero-chip {
            background: rgba(29, 78, 216, 0.08);
            color: var(--primary);
            padding: 8px 12px;
            border-radius: 999px;
            font-size: 0.88rem;
            font-weight: 600;
            border: 1px solid rgba(29, 78, 216, 0.10);
        }

        .section-title {
            font-size: 1.30rem;
            font-weight: 800;
            color: var(--text);
            margin-bottom: .6rem;
        }

        [data-testid="stTabs"] {
            margin-top: 0.35rem;
        }

        [data-testid="stTabs"] [role="tablist"] {
            gap: 8px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }

        [data-testid="stTabs"] [role="tab"] {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 8px 14px;
            color: var(--text) !important;
            font-weight: 600;
            height: auto;
        }

        [data-testid="stTabs"] [aria-selected="true"] {
            background: var(--primary-soft) !important;
            color: var(--primary) !important;
            border-color: #c9dbff !important;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border: 1px solid var(--border);
            padding: 16px 16px;
            border-radius: 18px;
            box-shadow: var(--shadow);
        }

        [data-testid="stMetricLabel"] {
            font-size: 0.84rem;
            color: var(--muted) !important;
            font-weight: 600;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.55rem;
            color: var(--text) !important;
            font-weight: 800;
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

        .small-note {
            font-size: 0.90rem;
            color: var(--muted);
            line-height: 1.6;
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 16px 18px;
        }

        .footer-note {
            color: var(--muted);
            font-size: 0.86rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


px.defaults.template = "plotly_white"


def brl(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def usd(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return "US$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def count_business_days(start: date, end: date) -> int:
    if end <= start:
        return 0
    return int(np.busday_count(start.isoformat(), end.isoformat()))


def forward_rate(
    spot: float,
    br_rate: float,
    us_rate: float,
    business_days: int,
    calendar_days: int,
) -> tuple[float, float, float]:
    br_factor = (1 + br_rate) ** (business_days / 252)
    us_factor = (1 + us_rate) ** (calendar_days / 360)
    forward = spot * br_factor / us_factor
    return forward, br_factor, us_factor


def ndf_pnl(
    settlement_fx: float,
    contracted_fx: float,
    notional_usd: float,
    direction: str,
) -> float:
    base = (settlement_fx - contracted_fx) * notional_usd
    return base if direction == "Compra de USD" else -base


def style_plotly(fig, y_title: str):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(color="#132238"),
        title_font=dict(size=18),
        xaxis_title="BRL por USD",
        yaxis_title=y_title,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=20),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#e8edf5", zeroline=False)
    return fig


with st.sidebar:
    st.markdown("## Parâmetros da operação")
    st.caption("Preencha abaixo os principais dados da simulação.")

    direction = st.selectbox(
        "Tipo de proteção",
        ["Compra de USD", "Venda de USD"],
        help="Compra de USD protege uma obrigação futura em dólar. Venda de USD protege um recebimento futuro.",
    )

    notional = st.number_input(
        "Nocional em USD",
        min_value=1_000.0,
        value=1_000_000.0,
        step=50_000.0,
        format="%.2f",
    )

    start_date = st.date_input("Data da operação", value=date.today())
    maturity_date = st.date_input(
        "Data de vencimento",
        value=date.today() + timedelta(days=180),
    )

    st.divider()

    spot = st.number_input(
        "Dólar spot (BRL/USD)",
        min_value=0.01,
        value=5.20,
        step=0.01,
        format="%.4f",
    )

    br_rate_pct = st.number_input(
        "Juros BRL a.a.",
        min_value=0.0,
        value=14.75,
        step=0.10,
        format="%.4f",
    )

    us_rate_pct = st.number_input(
        "Juros USD a.a.",
        min_value=0.0,
        value=4.50,
        step=0.10,
        format="%.4f",
    )

    st.divider()

    spread_mode = st.radio(
        "Forma de inserir o spread",
        ["Pontos de câmbio", "Percentual sobre o forward"],
        horizontal=False,
    )

    if spread_mode == "Pontos de câmbio":
        spread_points = st.number_input(
            "Spread do banco em pontos",
            value=0.0300,
            step=0.0050,
            format="%.4f",
        )
        spread_pct = 0.0
    else:
        spread_pct = st.number_input(
            "Spread do banco (%)",
            value=0.50,
            step=0.05,
            format="%.4f",
        ) / 100
        spread_points = 0.0

    use_manual_contract = st.checkbox("Informar taxa contratada manualmente")
    manual_contract = None
    if use_manual_contract:
        manual_contract = st.number_input(
            "Taxa contratada",
            min_value=0.01,
            value=5.50,
            step=0.01,
            format="%.4f",
        )

    st.divider()
    st.caption("Versão visual clara forçada para navegação mais limpa.")

if maturity_date <= start_date:
    st.error("A data de vencimento precisa ser posterior à data da operação.")
    st.stop()

calendar_days = (maturity_date - start_date).days
business_days = count_business_days(start_date, maturity_date)

br_rate = br_rate_pct / 100
us_rate = us_rate_pct / 100

fair_forward, br_factor, us_factor = forward_rate(
    spot=spot,
    br_rate=br_rate,
    us_rate=us_rate,
    business_days=business_days,
    calendar_days=calendar_days,
)

if spread_mode == "Pontos de câmbio":
    quoted_forward = (
        fair_forward + spread_points if direction == "Compra de USD" else fair_forward - spread_points
    )
else:
    quoted_forward = (
        fair_forward * (1 + spread_pct) if direction == "Compra de USD" else fair_forward * (1 - spread_pct)
    )

contracted_forward = manual_contract if manual_contract is not None else quoted_forward

implied_spread_points = (
    contracted_forward - fair_forward if direction == "Compra de USD" else fair_forward - contracted_forward
)
implied_spread_brl = implied_spread_points * notional
protected_value_brl = contracted_forward * notional

st.markdown(
    f"""
    <div class="hero-card">
        <div class="hero-title">Simulador de NDF e Hedge Cambial</div>
        <div class="hero-subtitle">MVP para precificação indicativa, análise de spread e simulação de resultado no vencimento.</div>
        <div class="hero-chips">
            <div class="hero-chip">{direction}</div>
            <div class="hero-chip">Nocional: {usd(notional, 0)}</div>
            <div class="hero-chip">Forward justo: {fair_forward:.4f}</div>
            <div class="hero-chip">Taxa considerada: {contracted_forward:.4f}</div>
            <div class="hero-chip">Prazo: {calendar_days} dias corridos</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

quick_1, quick_2, quick_3, quick_4 = st.columns(4)
quick_1.metric("Spot", f"{spot:.4f}")
quick_2.metric("Forward justo", f"{fair_forward:.4f}")
quick_3.metric("Taxa considerada", f"{contracted_forward:.4f}")
quick_4.metric("Valor protegido", brl(protected_value_brl, 0))

st.markdown('<div class="section-title">Análises da operação</div>', unsafe_allow_html=True)


tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Precificação",
        "Resultado no vencimento",
        "Hedge x sem hedge",
        "Memória de cálculo",
    ]
)

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Forward justo", f"{fair_forward:.4f}")
    c2.metric("Taxa considerada", f"{contracted_forward:.4f}")
    c3.metric("Forward points", f"{fair_forward - spot:.4f}")
    c4.metric("Spread implícito", f"{implied_spread_points:.4f}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Nocional", usd(notional, 0))
    c6.metric("Prazo corrido", f"{calendar_days} dias")
    c7.metric("Prazo útil", f"{business_days} dias")
    c8.metric("Custo implícito do spread", brl(implied_spread_brl, 0))

    st.subheader("Resumo da operação")
    summary_df = pd.DataFrame(
        {
            "Campo": [
                "Direção",
                "Spot",
                "Juros BRL",
                "Juros USD",
                "Forward justo",
                "Taxa simulada/contratada",
                "Diferença para o justo",
                "Valor protegido em R$",
            ],
            "Valor": [
                direction,
                f"{spot:.4f}",
                f"{br_rate_pct:.2f}% a.a.",
                f"{us_rate_pct:.2f}% a.a.",
                f"{fair_forward:.4f}",
                f"{contracted_forward:.4f}",
                f"{implied_spread_points:.4f}",
                brl(protected_value_brl, 0),
            ],
        }
    )
    st.dataframe(summary_df, hide_index=True, use_container_width=True)

    st.info(
        "Neste MVP, os dias úteis consideram apenas segunda a sexta. "
        "Feriados locais e convenções específicas de cada contrato devem ser incluídos na versão de produção."
    )

with tab2:
    st.subheader("Simulação de liquidação")

    default_settlement = float(round(contracted_forward * 1.05, 4))
    settlement_fx = st.number_input(
        "PTAX / taxa de referência no vencimento",
        min_value=0.01,
        value=default_settlement,
        step=0.01,
        format="%.4f",
    )

    pnl = ndf_pnl(
        settlement_fx=settlement_fx,
        contracted_fx=contracted_forward,
        notional_usd=notional,
        direction=direction,
    )

    r1, r2, r3 = st.columns(3)
    r1.metric("Taxa contratada", f"{contracted_forward:.4f}")
    r2.metric("Taxa no vencimento", f"{settlement_fx:.4f}")
    r3.metric("Resultado do NDF", brl(pnl, 0))

    low = max(0.10, contracted_forward * 0.80)
    high = contracted_forward * 1.20
    scenario_rates = np.linspace(low, high, 81)

    scenario_df = pd.DataFrame(
        {
            "Taxa no vencimento": scenario_rates,
            "Resultado do NDF": [ndf_pnl(x, contracted_forward, notional, direction) for x in scenario_rates],
        }
    )

    fig = px.line(
        scenario_df,
        x="Taxa no vencimento",
        y="Resultado do NDF",
        markers=False,
        title="Resultado financeiro por cenário de câmbio",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8")
    fig.add_vline(x=contracted_forward, line_dash="dash", line_color="#1d4ed8")
    style_plotly(fig, "Resultado em R$")
    st.plotly_chart(fig, use_container_width=True)

    sample_points = np.linspace(contracted_forward * 0.90, contracted_forward * 1.10, 9)
    sample_df = pd.DataFrame(
        {
            "Taxa no vencimento": [f"{x:.4f}" for x in sample_points],
            "Resultado do NDF": [brl(ndf_pnl(x, contracted_forward, notional, direction), 0) for x in sample_points],
        }
    )
    st.dataframe(sample_df, hide_index=True, use_container_width=True)

with tab3:
    st.subheader("Comparativo: exposição aberta x protegida")

    comparison_rates = np.linspace(contracted_forward * 0.85, contracted_forward * 1.15, 61)
    unhedged = comparison_rates * notional
    hedged = np.full_like(comparison_rates, contracted_forward * notional)

    if direction == "Compra de USD":
        y_title = "Custo total em R$"
        chart_title = "Custo da obrigação com e sem hedge"
    else:
        y_title = "Receita total em R$"
        chart_title = "Receita do recebimento com e sem hedge"

    hedge_df = pd.DataFrame(
        {
            "Taxa no vencimento": np.tile(comparison_rates, 2),
            "Valor em R$": np.concatenate([unhedged, hedged]),
            "Estratégia": ["Sem hedge"] * len(comparison_rates) + ["Com NDF"] * len(comparison_rates),
        }
    )

    fig2 = px.line(
        hedge_df,
        x="Taxa no vencimento",
        y="Valor em R$",
        color="Estratégia",
        title=chart_title,
    )
    style_plotly(fig2, y_title)
    st.plotly_chart(fig2, use_container_width=True)

    explanation = (
        "Para uma compra de USD, o NDF transforma o custo cambial variável em um custo aproximadamente fixo na taxa contratada."
        if direction == "Compra de USD"
        else "Para uma venda de USD, o NDF transforma a receita cambial variável em uma receita aproximadamente fixa na taxa contratada."
    )
    st.success(explanation)

with tab4:
    st.subheader("Memória de cálculo")

    calc_df = pd.DataFrame(
        {
            "Etapa": [
                "Dias corridos",
                "Dias úteis",
                "Fator BRL",
                "Fator USD",
                "Forward justo",
                "Spread aplicado",
                "Taxa final",
            ],
            "Cálculo / valor": [
                f"{calendar_days}",
                f"{business_days}",
                f"(1 + {br_rate:.6f}) ^ ({business_days}/252) = {br_factor:.8f}",
                f"(1 + {us_rate:.6f}) ^ ({calendar_days}/360) = {us_factor:.8f}",
                f"{spot:.4f} × ({br_factor:.8f} / {us_factor:.8f}) = {fair_forward:.4f}",
                f"{spread_points:.4f} ponto(s)" if spread_mode == "Pontos de câmbio" else f"{spread_pct * 100:.4f}%",
                f"{contracted_forward:.4f}",
            ],
        }
    )
    st.dataframe(calc_df, hide_index=True, use_container_width=True)

    st.markdown(
        """
        <div class="small-note">
            <strong>Fórmula-base do MVP</strong><br>
            Forward = Spot × Fator BRL ÷ Fator USD<br><br>
            Resultado para compra de USD = (taxa de liquidação − taxa contratada) × nocional.<br>
            Resultado para venda de USD = (taxa contratada − taxa de liquidação) × nocional.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()
st.markdown(
    '<div class="footer-note">Ferramenta indicativa para simulação. Não substitui confirmação de taxa, convenções contratuais, curvas de mercado, documentação jurídica ou validação da contraparte.</div>',
    unsafe_allow_html=True,
)
