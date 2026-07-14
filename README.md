# Simulador NDF - MVP

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Observação importante

Esta versão já inclui um arquivo `.streamlit/config.toml` para **forçar o app em modo claro**.

## Escopo atual

- Precificação indicativa por diferencial de juros
- Compra e venda de USD
- Spread em pontos ou percentual
- Resultado no vencimento
- Comparação hedge x sem hedge
- Memória de cálculo
- Visual mais limpo e 100% claro

## Próximas evoluções

- Calendário de feriados
- Curva DI e curva USD por vértice
- PTAX automática
- Mark-to-market
- Carteira de contratos
- Exportação Excel/PDF
