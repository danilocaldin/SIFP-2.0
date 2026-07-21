"""
domain/categories.py
---------------------
A taxonomia de categorias é um conceito de domínio — tanto a camada de
inteligência (categorização automática) quanto a de persistência
(schema, opções do dropdown na UI) precisam dela, então vive aqui em vez
de em uma das duas, evitando que uma dependa da outra.
"""

CATEGORIA_NAO_CATEGORIZADO = "Não categorizado"

# Transferências que o titular faz para si mesmo (ex: para uma conta
# investimento e de volta) não são receita nem despesa real — é o mesmo
# dinheiro mudando de lugar. Categoria própria para que os serviços de
# indicadores possam excluí-la dos totais de Receita/Despesa/Saldo.
SELF_TRANSFER_CATEGORY = "Transferência entre contas próprias"

CATEGORIAS_PADRAO = [
    "Mercado",
    "Transporte",
    "Lazer",
    "Moradia",
    "Saúde",
    "Educação",
    "Alimentação",
    "Salário/Receita",
    "Assinaturas",
    "Compras",
    "Transferências",
    SELF_TRANSFER_CATEGORY,
    "Investimentos",
    "Contas",
    "Tarifas",
    "Cuidados Pessoais",
    "Dívida",          # transferências para terceiros que representam dívida (ex: empréstimo pessoal informal)
    "Ajuda Familiar",  # transferências de apoio financeiro a familiares
    "Outros",
    CATEGORIA_NAO_CATEGORIZADO,
]
