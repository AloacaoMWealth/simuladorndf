# Simulador de NDF / Trava Cambial - V5

## Como executar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura desta versão

- tela única e objetiva;
- compra para importação ou venda para exportação;
- consulta automática da PTAX mais recente pelo serviço OData do Banco Central;
- fallback para preenchimento manual se a API estiver indisponível;
- seleção entre PTAX média, compra ou venda;
- taxa NDF manual, calculada por over spot ou taxa a termo indicativa;
- vencimento, dias corridos e dias úteis estimados;
- taxa travada, over spot e equivalente em reais;
- cenário de USD/BRL no vencimento;
- payoff de compra e venda;
- geração de PDF da simulação;
- metodologia e memória de cálculo escondidas em um expander;
- modo claro forçado.

## Observação importante

A opção `Taxa a termo indicativa` utiliza juros simples em Dias/360 apenas como referência didática:

```text
Forward = Spot × (1 + juros BRL × dias/360) / (1 + juros USD × dias/360)
```

Para uma simulação comercial ou contratual, o modo recomendado é `Taxa negociada / manual`, com a taxa efetivamente cotada pela contraparte.

## PTAX

A aplicação consulta o endpoint oficial do serviço PTAX/OData do Banco Central e prioriza o registro classificado como `Fechamento PTAX`. Se a consulta falhar, o campo de spot permanece editável.
