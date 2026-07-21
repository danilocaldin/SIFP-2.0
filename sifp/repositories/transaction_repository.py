"""
repositories/transaction_repository.py
-----------------------------------------
Acesso a dados da tabela transactions. Toda query SQL relacionada a
transações vive aqui — nenhuma outra camada monta SQL diretamente.

Essa tabela cumpre DUAS funções ao mesmo tempo:
  1) É o "extrato consolidado" que alimenta indicadores e dashboard.
  2) É o dataset de treino do modelo de ML e a memória por descrição
     (toda transação com human_confirmed=1 vira um exemplo de treino e
     entra em get_learned_categories()).
"""

import hashlib
import sqlite3
from pathlib import Path

import pandas as pd

from sifp.domain.categories import CATEGORIA_NAO_CATEGORIZADO
from sifp.repositories.connection import DEFAULT_DB_PATH, get_connection


def make_tx_hash(date: str, description: str, value: float) -> str:
    """
    Identificador único e estável para a transação — evita duplicar
    lançamentos quando o mesmo extrato (ou um período sobreposto) é
    importado mais de uma vez.
    """
    raw = f"{date}|{description.strip().upper()}|{round(value, 2)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


class TransactionRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    def insert_new(self, df: pd.DataFrame, source_file: str = "") -> int:
        """Insere transações novas; ignora as que já existem (dedup por hash).
        Retorna quantas linhas novas foram efetivamente inseridas."""
        conn = self._connect()
        cur = conn.cursor()
        inserted = 0
        for _, row in df.iterrows():
            # Normaliza pra um único formato de string ("%Y-%m-%d %H:%M")
            # antes de gravar — a coluna date é TEXT sem tipo fixo, e
            # get_all() lê de volta com parse_dates (o pandas infere o
            # formato pela maioria das linhas). Se importadores diferentes
            # gravassem formatos diferentes, o formato minoritário viraria
            # NaT silenciosamente e corromperia indicadores calculados a
            # partir dessa transação. Normalizar aqui, no único ponto de
            # inserção, protege qualquer importador atual ou futuro
            # (Inter/Nubank/Santander/XP estão planejados).
            date_normalized = pd.to_datetime(row["date"]).strftime("%Y-%m-%d %H:%M")
            tx_hash = make_tx_hash(date_normalized, row["description"], row["value"])
            try:
                cur.execute(
                    """
                    INSERT INTO transactions
                        (tx_hash, date, description, value, category, confidence,
                         source_file, bank_category, self_transfer, merchant, category_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx_hash,
                        date_normalized,
                        row["description"],
                        float(row["value"]),
                        row.get("category", CATEGORIA_NAO_CATEGORIZADO),
                        float(row.get("confidence", 0.0)),
                        source_file,
                        row.get("bank_category", "") or "",
                        int(bool(row.get("self_transfer", False))),
                        row.get("merchant", "") or "",
                        row.get("category_source", "") or "",
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue  # tx_hash já existe -> duplicada, ignora
        conn.commit()
        conn.close()
        return inserted

    def get_all(self) -> pd.DataFrame:
        conn = self._connect()
        df = pd.read_sql_query(
            "SELECT * FROM transactions ORDER BY date DESC", conn, parse_dates=["date"]
        )
        conn.close()
        return df

    def get_training_data(self) -> pd.DataFrame:
        """Transações já classificadas manualmente, usadas para treinar o modelo de ML."""
        conn = self._connect()
        df = pd.read_sql_query(
            """
            SELECT description, category FROM transactions
            WHERE category IS NOT NULL AND category != ?
            """,
            conn,
            params=(CATEGORIA_NAO_CATEGORIZADO,),
        )
        conn.close()
        return df

    def update_category(self, tx_hash: str, new_category: str) -> None:
        """Atualiza a categoria de uma transação e marca como confirmada por humano."""
        self.bulk_update_categories([(tx_hash, new_category)])

    def bulk_update_categories(self, updates: list[tuple[str, str]]) -> None:
        """
        updates: lista de (tx_hash, categoria_confirmada). Marca
        human_confirmed=1 — chamado tanto para transações corrigidas
        quanto para as revisadas e mantidas como estavam (o próprio ato
        de revisar e salvar é a confirmação).

        Exceção deliberada: se a categoria final ainda é
        'Não categorizado', NÃO marca como confirmada. "Confirmar que não
        tem categoria" é uma contradição — a linha só estava visível na
        tela porque ainda não foi decidida, e marcá-la como human_confirmed
        faria a memória por descrição (get_learned_categories) tratar
        'Não categorizado' como a categoria estável dela, escondendo-a de
        futuras revisões sem ela ter sido realmente categorizada.
        """
        conn = self._connect()
        cur = conn.cursor()
        confirmed = [(cat, h) for h, cat in updates if cat != CATEGORIA_NAO_CATEGORIZADO]
        unresolved = [(cat, h) for h, cat in updates if cat == CATEGORIA_NAO_CATEGORIZADO]

        if confirmed:
            cur.executemany(
                "UPDATE transactions SET category = ?, confidence = 1.0, human_confirmed = 1, "
                "category_source = 'human' WHERE tx_hash = ?",
                confirmed,
            )
        if unresolved:
            cur.executemany(
                "UPDATE transactions SET category = ?, confidence = 0.0, human_confirmed = 0, "
                "category_source = 'none' WHERE tx_hash = ?",
                unresolved,
            )
        conn.commit()
        conn.close()

    def get_learned_categories(self) -> dict:
        """
        Constrói a "memória" do sistema a partir de todas as transações
        que o usuário já confirmou manualmente, agrupadas por descrição
        exata.

        Para cada descrição:
          - categoria sempre igual -> "estável":
            {"category": "Mercado", "variable": False, "history": [("Mercado", 5)]}
          - categorias diferentes ao longo do tempo (ex: Pix para a mesma
            pessoa que às vezes é uma coisa, às vezes é outra) -> "variável":
            {"category": None, "variable": True, "history": [("Moradia", 2), ("Lazer", 1)]}
            Fica sempre marcada para revisão manual — o histórico prova
            que a descrição não tem significado fixo.
        """
        conn = self._connect()
        df = pd.read_sql_query(
            """
            SELECT description, category, COUNT(*) as n
            FROM transactions
            WHERE human_confirmed = 1
            GROUP BY description, category
            """,
            conn,
        )
        conn.close()

        learned = {}
        for desc, group in df.groupby("description"):
            history = sorted(zip(group["category"], group["n"]), key=lambda x: x[1], reverse=True)
            if len(history) == 1:
                learned[desc] = {"category": history[0][0], "variable": False, "history": history}
            else:
                learned[desc] = {"category": None, "variable": True, "history": history}
        return learned
