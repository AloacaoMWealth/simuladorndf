
from __future__ import annotations

from datetime import date, timedelta
import math

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Simulador NDF | Hedge Cambial",
    page_icon="💱",
    layout="wide",
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e8e8e8;
            padding: 14px 16px;
            border-radius: 12px;
        }
        [data-testid="stMetricLabel"] {font-size: 0.86rem;}
        [data-testid="stMetricValue"] {font-size: 1.55rem;}
        .small-note {
            font-size: 0.84rem;
            color: #666;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def brl(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return "R$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def usd(value: float, decimals: int = 2) -> str:
    text = f"{value:,.{decimals}f}"
    return "US$ " + text.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float, decimals: int = 2) -> str:
    return f"{value * 100:.{decimals}f}%".replace(".", ",")


def count_business_days(start: date, end: date) -> int:
    """MVP: conta segunda a sexta; feriados entram numa versão posterior."""
    if end <= start:
        return 0
    days = np.busday_count(start.isoformat(), end.isoformat())
    return int(days)


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


st.title("Simulador de NDF e Hedge Cambial")
st.caption(
    "MVP para precificação indicativa, análise de spread e simulação de resultado no vencimento."
)

with st.sidebar:
    st.header("Parâmetros da operação")

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
        fair_forward + spread_points
        if direction == "Compra de USD"
        else fair_forward - spread_points
    )
else:
    quoted_forward = (
        fair_forward * (1 + spread_pct)
        if direction == "Compra de USD"
        else fair_forward * (1 - spread_pct)
    )

contracted_forward = manual_contract if manual_contract is not None else quoted_forward

implied_spread_points = (
    contracted_forward - fair_forward
    if direction == "Compra de USD"
    else fair_forward - contracted_forward
)
implied_spread_brl = implied_spread_points * notional

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
            ],
            "Valor": [
                direction,
                f"{spot:.4f}",
                f"{br_rate_pct:.2f}% a.a.",
                f"{us_rate_pct:.2f}% a.a.",
                f"{fair_forward:.4f}",
                f"{contracted_forward:.4f}",
                f"{implied_spread_points:.4f}",
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
            "Resultado do NDF": [
                ndf_pnl(x, contracted_forward, notional, direction)
                for x in scenario_rates
            ],
        }
    )

    fig = px.line(
        scenario_df,
        x="Taxa no vencimento",
        y="Resultado do NDF",
        markers=False,
        title="Resultado financeiro por cenário de câmbio",
    )
    fig.add_hline(y=0, line_dash="dash")
    fig.add_vline(x=contracted_forward, line_dash="dash")
    fig.update_layout(
        xaxis_title="BRL por USD",
        yaxis_title="Resultado em R$",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    sample_points = np.linspace(contracted_forward * 0.90, contracted_forward * 1.10, 9)
    sample_df = pd.DataFrame(
        {
            "Taxa no vencimento": [f"{x:.4f}" for x in sample_points],
            "Resultado do NDF": [
                brl(ndf_pnl(x, contracted_forward, notional, direction), 0)
                for x in sample_points
            ],
        }
    )
    st.dataframe(sample_df, hide_index=True, use_container_width=True)

with tab3:
    st.subheader("Comparativo: exposição aberta x protegida")

    comparison_rates = np.linspace(contracted_forward * 0.85, contracted_forward * 1.15, 61)

    if direction == "Compra de USD":
        unhedged = comparison_rates * notional
        hedged = np.full_like(comparison_rates, contracted_forward * notional)
        y_title = "Custo total em R$"
        chart_title = "Custo da obrigação com e sem hedge"
    else:
        unhedged = comparison_rates * notional
        hedged = np.full_like(comparison_rates, contracted_forward * notional)
        y_title = "Receita total em R$"
        chart_title = "Receita do recebimento com e sem hedge"

    hedge_df = pd.DataFrame(
        {
            "Taxa no vencimento": np.tile(comparison_rates, 2),
            "Valor em R$": np.concatenate([unhedged, hedged]),
            "Estratégia": ["Sem hedge"] * len(comparison_rates)
            + ["Com NDF"] * len(comparison_rates),
        }
    )

    fig2 = px.line(
        hedge_df,
        x="Taxa no vencimento",
        y="Valor em R$",
        color="Estratégia",
        title=chart_title,
    )
    fig2.update_layout(
        xaxis_title="BRL por USD",
        yaxis_title=y_title,
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)

    explanation = (
        "Para uma compra de USD, o NDF transforma o custo cambial variável em um custo "
        "aproximadamente fixo na taxa contratada."
        if direction == "Compra de USD"
        else
        "Para uma venda de USD, o NDF transforma a receita cambial variável em uma receita "
        "aproximadamente fixa na taxa contratada."
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
                (
                    f"{spread_points:.4f} ponto(s)"
                    if spread_mode == "Pontos de câmbio"
                    else f"{spread_pct * 100:.4f}%"
                ),
                f"{contracted_forward:.4f}",
            ],
        }
    )
    st.dataframe(calc_df, hide_index=True, use_container_width=True)

    st.markdown(
        """
        <div class="small-note">
        Fórmula-base do MVP:<br>
        Forward = Spot × Fator BRL ÷ Fator USD<br><br>
        Resultado para compra de USD = (taxa de liquidação − taxa contratada) × nocional.<br>
        Resultado para venda de USD = (taxa contratada − taxa de liquidação) × nocional.
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()
st.caption(
    "Ferramenta indicativa para simulação. Não substitui confirmação de taxa, convenções contratuais, "
    "curvas de mercado, documentação jurídica ou validação da contraparte."
)
