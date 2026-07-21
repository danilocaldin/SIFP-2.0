"""
importers/base.py
------------------
Interface comum que todo importador de extrato deve implementar
(Módulo 1). Hoje só existe BTGImporter; Inter/Nubank/Santander/XP entram
depois implementando a mesma interface, sem tocar em nenhuma outra camada
do sistema (services, repositories, UI continuam iguais).
"""

from abc import ABC, abstractmethod

import pandas as pd


class StatementImporter(ABC):
    """
    Contrato: ler um arquivo de extrato e devolver dados já normalizados
    (Módulo 2) — nunca formato bruto do banco.
    """

    institution_name: str = "Desconhecida"

    @abstractmethod
    def supports(self, filename: str) -> bool:
        """True se este importador sabe ler o arquivo, a partir do nome/extensão."""

    @abstractmethod
    def read(self, uploaded_file) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Lê o arquivo e retorna (transacoes, saldos_diarios) normalizados:
          - transacoes: date, description, value, bank_category, self_transfer
          - saldos_diarios: date, balance (pode vir vazio se o formato não
            trouxer essa informação)

        Levanta ValueError com mensagem amigável se o arquivo não puder
        ser interpretado.
        """
