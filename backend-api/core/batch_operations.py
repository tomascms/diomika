"""Operações em batch com validação de duplicados e idempotência.

Casos de Uso:
1. Upload CSV de produtos
2. Import de modelos
3. Atualização em massa com fallback individual
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("diomika-api")


@dataclass
class BatchItemResult:
    """Resultado de operação individual no batch."""

    index: int                    # Posição no batch (0-based)
    status: str                   # "success" | "error" | "skipped" | "conflict"
    data: Optional[dict] = None   # Resultado da operação (se sucesso)
    error: Optional[str] = None   # Mensagem de erro
    reason: Optional[str] = None  # Motivo skip/conflict


@dataclass
class BatchOperationResult:
    """Resultado de operação batch completa."""

    total: int                           # Total de items
    successful: int                      # Sucesso
    failed: int                          # Erro
    skipped: int                         # Pulados (duplicado, etc)
    conflicts: int                       # Conflitos de negócio
    items: list[BatchItemResult]         # Resultados individuais
    duration_ms: float                   # Tempo total

    @property
    def success_rate(self) -> float:
        """Taxa de sucesso (0.0 - 1.0)."""
        if self.total == 0:
            return 0.0
        return self.successful / self.total

    @property
    def is_fully_successful(self) -> bool:
        """Todos os items foram processados com sucesso."""
        return self.failed == 0 and self.skipped == 0 and self.conflicts == 0

    def get_failed_items(self) -> list[BatchItemResult]:
        """Retorna apenas items falhados."""
        return [item for item in self.items if item.status == "error"]

    def get_skipped_items(self) -> list[BatchItemResult]:
        """Retorna items pulados."""
        return [item for item in self.items if item.status == "skipped"]

    def get_conflict_items(self) -> list[BatchItemResult]:
        """Retorna items com conflito."""
        return [item for item in self.items if item.status == "conflict"]


class DuplicateDetector:
    """Detecta duplicados em batch operações."""

    @staticmethod
    def find_duplicate_fields(
        items: list[dict],
        key_fields: list[str],
    ) -> dict[str, list[int]]:
        """
        Detecta duplicados baseado em campos-chave.

        Args:
        - items: Lista de dicts
        - key_fields: Campos a comparar (ex: ["ean"], ["id_modelo", "altura"])

        Returns:
        - Dict mapping key -> lista de indices duplicados

        Exemplo:
            items = [
                {"ean": "111", "nome": "A"},
                {"ean": "111", "nome": "B"},  # Duplicado!
                {"ean": "222", "nome": "C"},
            ]
            duplicates = DuplicateDetector.find_duplicate_fields(items, ["ean"])
            # {"111": [0, 1]}
        """
        from collections import defaultdict

        duplicates = defaultdict(list)

        for idx, item in enumerate(items):
            key_values = tuple(str(item.get(f, "")).strip() for f in key_fields)
            key = "|".join(key_values)

            if key:  # Ignora chaves vazias
                duplicates[key].append(idx)

        # Retorna apenas chaves com múltiplos indices
        return {k: v for k, v in duplicates.items() if len(v) > 1}

    @staticmethod
    def find_db_conflicts(
        db_query_fn: Callable[[dict], bool],
        items: list[dict],
        key_fields: list[str],
    ) -> dict[int, str]:
        """
        Detecta conflitos com registos existentes em BD.

        Args:
        - db_query_fn: Função que retorna True se existe conflito
        - items: Items a verificar
        - key_fields: Campos a usar na query

        Returns:
        - Dict mapping index -> motivo do conflito

        Exemplo:
            def check_ean(item):
                return db.table("products").select("id").eq("ean", item["ean"]).limit(1).execute().data

            conflicts = DuplicateDetector.find_db_conflicts(check_ean, items, ["ean"])
            # {0: "EAN já existe em BD", 1: "..."}
        """
        conflicts = {}

        for idx, item in enumerate(items):
            try:
                if db_query_fn(item):
                    key_value = "|".join(str(item.get(f, "")) for f in key_fields)
                    conflicts[idx] = f"Conflito com registo existente: {key_value}"
            except Exception as exc:
                conflicts[idx] = f"Erro ao verificar conflito: {str(exc)}"

        return conflicts


class BatchProcessor:
    """Processa operações em batch com retry e fallback."""

    @staticmethod
    def process_batch(
        items: list[dict],
        operation_fn: Callable[[dict, int], tuple[bool, Any, Optional[str]]],
        *,
        check_duplicates: Optional[list[str]] = None,
        check_db_conflicts: Optional[Callable] = None,
        stop_on_first_error: bool = False,
    ) -> BatchOperationResult:
        """
        Processa batch de operações.

        Args:
        - items: Lista de dicts a processar
        - operation_fn: Função(item, index) -> (success, data, error_msg)
        - check_duplicates: Campos a verificar duplicados (ex: ["ean"])
        - check_db_conflicts: Função para verificar conflitos em BD
        - stop_on_first_error: Para na primeira falha

        Returns:
        - BatchOperationResult com status completo
        """
        import time

        start_time = time.time()
        results = []

        # Verificar duplicados internos
        internal_dupes = {}
        if check_duplicates:
            internal_dupes = DuplicateDetector.find_duplicate_fields(items, check_duplicates)

        # Verificar conflitos em BD
        db_conflicts = {}
        if check_db_conflicts:
            db_conflicts = DuplicateDetector.find_db_conflicts(
                check_db_conflicts, items, check_duplicates or ["id"]
            )

        # Processar items
        for idx, item in enumerate(items):
            try:
                # Verificar duplicado interno
                key_value = "|".join(str(item.get(f, "")) for f in (check_duplicates or ["id"]))
                if key_value in internal_dupes and internal_dupes[key_value][0] != idx:
                    # Este item é duplicado de outro anterior
                    results.append(BatchItemResult(
                        index=idx,
                        status="skipped",
                        reason=f"Duplicado do index {internal_dupes[key_value][0]}"
                    ))
                    continue

                # Verificar conflito em BD
                if idx in db_conflicts:
                    results.append(BatchItemResult(
                        index=idx,
                        status="conflict",
                        reason=db_conflicts[idx]
                    ))
                    continue

                # Executar operação
                success, data, error = operation_fn(item, idx)

                if success:
                    results.append(BatchItemResult(
                        index=idx,
                        status="success",
                        data=data
                    ))
                else:
                    results.append(BatchItemResult(
                        index=idx,
                        status="error",
                        error=error
                    ))
                    if stop_on_first_error:
                        break

            except Exception as exc:
                logger.exception(f"Batch item {idx} exception: {exc}")
                results.append(BatchItemResult(
                    index=idx,
                    status="error",
                    error=f"Exception: {str(exc)}"
                ))
                if stop_on_first_error:
                    break

        # Compilar resultado
        elapsed_ms = (time.time() - start_time) * 1000

        return BatchOperationResult(
            total=len(items),
            successful=sum(1 for r in results if r.status == "success"),
            failed=sum(1 for r in results if r.status == "error"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            conflicts=sum(1 for r in results if r.status == "conflict"),
            items=results,
            duration_ms=elapsed_ms,
        )


class BatchOperationAuditor:
    """Auditoria de operações batch."""

    @staticmethod
    def log_batch_result(
        batch_id: str,
        table_name: str,
        result: BatchOperationResult,
    ) -> None:
        """Log auditoria para batch operation."""
        logger.info(
            f"Batch operation: id={batch_id}, table={table_name}, "
            f"total={result.total}, success={result.successful}, "
            f"failed={result.failed}, skipped={result.skipped}, "
            f"conflicts={result.conflicts}, duration_ms={result.duration_ms:.1f}"
        )

    @staticmethod
    def log_batch_failures(
        batch_id: str,
        table_name: str,
        result: BatchOperationResult,
    ) -> None:
        """Log detalhado de falhas."""
        if not result.get_failed_items():
            return

        for item in result.get_failed_items():
            logger.warning(
                f"Batch item failed: batch_id={batch_id}, table={table_name}, "
                f"index={item.index}, error={item.error}"
            )
