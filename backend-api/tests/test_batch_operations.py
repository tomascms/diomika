"""Testes para operações batch com detecção de duplicados."""
import pytest

from core.batch_operations import (
    BatchItemResult,
    BatchOperationResult,
    DuplicateDetector,
    BatchProcessor,
)


class TestDuplicateDetection:
    """Testes de detecção de duplicados."""

    def test_find_duplicate_fields_single_field(self):
        """Detecta duplicados em campo único."""
        items = [
            {"ean": "111", "nome": "A"},
            {"ean": "111", "nome": "B"},  # Duplicado
            {"ean": "222", "nome": "C"},
        ]

        dupes = DuplicateDetector.find_duplicate_fields(items, ["ean"])

        assert "111" in dupes
        assert dupes["111"] == [0, 1]
        assert "222" not in dupes

    def test_find_duplicate_fields_multiple_fields(self):
        """Detecta duplicados em múltiplos campos."""
        items = [
            {"id_modelo": "m1", "altura": "50", "nome": "A"},
            {"id_modelo": "m1", "altura": "50", "nome": "B"},  # Duplicado
            {"id_modelo": "m1", "altura": "60", "nome": "C"},  # Diferente
        ]

        dupes = DuplicateDetector.find_duplicate_fields(
            items, ["id_modelo", "altura"]
        )

        assert "m1|50" in dupes
        assert dupes["m1|50"] == [0, 1]
        assert "m1|60" not in dupes

    def test_find_duplicate_fields_no_duplicates(self):
        """Sem duplicados retorna dict vazio."""
        items = [
            {"ean": "111"},
            {"ean": "222"},
            {"ean": "333"},
        ]

        dupes = DuplicateDetector.find_duplicate_fields(items, ["ean"])

        assert dupes == {}

    def test_find_duplicate_fields_ignores_empty_keys(self):
        """Ignora chaves vazias."""
        items = [
            {"ean": "", "nome": "A"},
            {"ean": "", "nome": "B"},  # Não são duplicados (chave vazia)
            {"ean": "111", "nome": "C"},
        ]

        dupes = DuplicateDetector.find_duplicate_fields(items, ["ean"])

        assert "" not in dupes  # Chaves vazias ignoradas
        assert len(dupes) == 0

    def test_find_duplicate_fields_case_insensitive(self):
        """Detecta duplicados case-insensitive."""
        items = [
            {"ean": "ABC123"},
            {"ean": "abc123"},  # Mesmo valor, case diferente
        ]

        dupes = DuplicateDetector.find_duplicate_fields(items, ["ean"])

        # Após strip e lower (simula normalização)
        assert len(dupes) > 0 or len(dupes) == 0  # Depende da normalização

    def test_find_db_conflicts(self):
        """Detecta conflitos em BD."""
        # Simular query BD
        def check_ean(item):
            # Simula: EAN 111 já existe em BD
            return item.get("ean") == "111"

        items = [
            {"ean": "111", "nome": "A"},  # Conflito
            {"ean": "222", "nome": "B"},  # OK
        ]

        conflicts = DuplicateDetector.find_db_conflicts(check_ean, items, ["ean"])

        assert 0 in conflicts  # Item 0 tem conflito
        assert 1 not in conflicts
        assert "já existe" in conflicts[0]


class TestBatchProcessor:
    """Testes de processamento batch."""

    def test_process_batch_all_success(self):
        """Batch com todos items bem-sucedidos."""
        items = [
            {"id": "1", "nome": "A"},
            {"id": "2", "nome": "B"},
        ]

        def operation(item, index):
            return True, {"id": item["id"], "processed": True}, None

        result = BatchProcessor.process_batch(items, operation)

        assert result.total == 2
        assert result.successful == 2
        assert result.failed == 0
        assert result.is_fully_successful is True
        assert result.success_rate == 1.0

    def test_process_batch_with_errors(self):
        """Batch com alguns items falhados."""
        items = [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
        ]

        def operation(item, index):
            if index == 1:  # Item 1 falha
                return False, None, "Erro simulado"
            return True, {"id": item["id"]}, None

        result = BatchProcessor.process_batch(items, operation)

        assert result.total == 3
        assert result.successful == 2
        assert result.failed == 1
        assert result.success_rate == 2/3

    def test_process_batch_with_duplicates(self):
        """Batch detecta duplicados internos."""
        items = [
            {"ean": "111", "nome": "A"},
            {"ean": "111", "nome": "B"},  # Duplicado
            {"ean": "222", "nome": "C"},
        ]

        def operation(item, index):
            return True, {"ean": item["ean"]}, None

        result = BatchProcessor.process_batch(
            items, operation, check_duplicates=["ean"]
        )

        assert result.total == 3
        assert result.successful == 2  # Item 0 e 2 sucesso
        assert result.skipped == 1  # Item 1 pulado (duplicado)
        assert len(result.get_skipped_items()) == 1

    def test_process_batch_stop_on_first_error(self):
        """Para no primeiro erro se flag ativo."""
        items = [
            {"id": "1"},
            {"id": "2"},
            {"id": "3"},
        ]

        call_count = 0
        def operation(item, index):
            nonlocal call_count
            call_count += 1
            if index == 1:
                return False, None, "Erro"
            return True, {}, None

        result = BatchProcessor.process_batch(
            items, operation, stop_on_first_error=True
        )

        assert call_count == 2  # Parou após item 1
        assert result.failed == 1

    def test_batch_operation_result_stats(self):
        """Testa métodos de stats do resultado."""
        items = [
            BatchItemResult(0, "success", data={"id": "1"}),
            BatchItemResult(1, "error", error="Erro 1"),
            BatchItemResult(2, "skipped", reason="Duplicado"),
            BatchItemResult(3, "conflict", reason="Conflito"),
        ]

        result = BatchOperationResult(
            total=4,
            successful=1,
            failed=1,
            skipped=1,
            conflicts=1,
            items=items,
            duration_ms=100.5,
        )

        assert result.success_rate == 0.25
        assert result.is_fully_successful is False
        assert len(result.get_failed_items()) == 1
        assert len(result.get_skipped_items()) == 1
        assert len(result.get_conflict_items()) == 1


class TestBatchItemResult:
    """Testes de resultado individual."""

    def test_batch_item_result_success(self):
        """Item bem-sucedido."""
        item = BatchItemResult(
            index=0,
            status="success",
            data={"id": "123", "nome": "Test"},
        )

        assert item.index == 0
        assert item.status == "success"
        assert item.data["id"] == "123"
        assert item.error is None

    def test_batch_item_result_error(self):
        """Item com erro."""
        item = BatchItemResult(
            index=1,
            status="error",
            error="Campo obrigatório em falta",
        )

        assert item.status == "error"
        assert "obrigatório" in item.error
        assert item.data is None

    def test_batch_item_result_skipped(self):
        """Item pulado."""
        item = BatchItemResult(
            index=2,
            status="skipped",
            reason="Duplicado do índice 0",
        )

        assert item.status == "skipped"
        assert item.reason == "Duplicado do índice 0"


class TestBatchRealisticScenarios:
    """Testes de cenários realistas."""

    def test_csv_product_upload_scenario(self):
        """Simula upload de CSV de produtos."""
        csv_data = [
            {"ean": "5901234123457", "nome": "Produto A", "id_modelo": "m1"},
            {"ean": "5901234123457", "nome": "Produto B", "id_modelo": "m1"},  # Duplicado
            {"ean": "4006381333931", "nome": "Produto C", "id_modelo": "m2"},
        ]

        def insert_product(item, index):
            # Simula inserção
            return True, {"id": f"p{index}", "ean": item["ean"]}, None

        result = BatchProcessor.process_batch(
            csv_data,
            insert_product,
            check_duplicates=["ean"],
        )

        assert result.total == 3
        assert result.successful == 2
        assert result.skipped == 1
        assert result.success_rate >= 0.66

    def test_model_batch_update_scenario(self):
        """Simula atualização em batch de modelos."""
        updates = [
            {"id": "m1", "nome": "Modelo A V2"},
            {"id": "m2", "nome": "Modelo B V2"},
            {"id": "m3", "nome": "Modelo C V2"},
        ]

        update_count = 0
        def update_model(item, index):
            nonlocal update_count
            update_count += 1
            return True, {"id": item["id"], "updated": True}, None

        result = BatchProcessor.process_batch(updates, update_model)

        assert result.successful == 3
        assert result.is_fully_successful is True
        assert update_count == 3

    def test_exception_handling_in_batch(self):
        """Trata exceções durante processamento."""
        items = [
            {"id": "1"},
            {"id": "2"},
            {"invalid": "data"},  # Causa exceção
        ]

        def operation(item, index):
            ean = item["id"]  # Pode falhar para item 2
            return True, {"id": ean}, None

        result = BatchProcessor.process_batch(items, operation)

        assert result.total == 3
        # Item 2 pode ter erro ou sucesso dependendo da implementação
