# Simulador NDF - MVP Validado

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

## O que mudou nesta versão

- layout mais enxuto e objetivo
- datas em DD/MM/AAAA
- números formatados no padrão brasileiro
- memória de cálculo em expander
- fórmula de taxa a termo ajustada para **bater com a calculadora de referência**
- convenção usada: **juros simples com base Dias/360**

## Fórmula usada

Para o par informado:

```text
Forward = Spot × (1 + juros_moeda_cotada × dias/base) / (1 + juros_moeda_base × dias/base)
```

## Validação enviada pelo usuário

Com os parâmetros:
- USD/BRL
- spot = 5,0725
- juros base = 3,75%
- juros cotada = 14,25%
- dias = 360

resultado esperado:
- taxa a termo = 5,585861
- termo em pontos = 0,513361
- pips = 5.133,61

A app está ajustada para reproduzir essa lógica.
