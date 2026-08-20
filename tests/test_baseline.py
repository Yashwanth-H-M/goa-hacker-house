from pathlib import Path
import tempfile
import unittest

from src.chunking import chunk_records
from src.data import PassageRecord, load_jsonl
from src.pipeline import TextRAGPipeline
from src.retrieval import HybridIndex


FIXTURE = Path("tests/fixtures/mini_msmarco_xi.jsonl")


class BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        records = load_jsonl(FIXTURE)
        chunks = chunk_records(records, strategy="sentence", chunk_size=32)
        self.index = HybridIndex(chunks, dimensions=64, rrf_k=60)

    def test_fixture_records_preserve_selected_labels(self) -> None:
        records = load_jsonl(FIXTURE)
        self.assertEqual(len(records), 4)
        self.assertEqual(sum(record.selected is True for record in records), 3)

    def test_hybrid_retrieval_surfaces_rag_context(self) -> None:
        results = self.index.search("How does retrieval augmented generation reduce unsupported claims?", top_k=2)
        self.assertTrue(results)
        self.assertTrue(results[0].chunk.selected)
        self.assertIn("retrieves relevant source passages", results[0].chunk.text)

    def test_index_artifact_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.index.save(directory, strategy="sentence")
            restored = HybridIndex.load(directory)
            results = restored.search("What does BM25 weight?", top_k=1)
        self.assertEqual(results[0].chunk.parent_passage_id, "hi:101:0")

    def test_high_similarity_floor_produces_refusal(self) -> None:
        pipeline = TextRAGPipeline(self.index, minimum_similarity=1.0)
        response = pipeline.query("A completely unrelated request", top_k=2)
        self.assertTrue(response.refused)
        self.assertEqual(response.cited_chunk_ids, [])
        self.assertEqual(response.path_taken, "refusal")

    def test_weak_keyword_only_match_is_refused(self) -> None:
        response = TextRAGPipeline(self.index).query("What is an unrelated capital city?", top_k=2)
        self.assertTrue(response.refused)
        self.assertEqual(response.cited_chunk_ids, [])
        self.assertEqual(response.generation_status, "skipped_insufficient_evidence")

    def test_evidence_backed_lexical_query_remains_available(self) -> None:
        response = TextRAGPipeline(self.index).query("What is BM25?", top_k=2)
        self.assertFalse(response.refused)
        self.assertEqual(response.path_taken, "verified_retrieval")
        self.assertTrue(response.cited_chunk_ids)

    def test_unsafe_instruction_is_refused_before_retrieval(self) -> None:
        response = TextRAGPipeline(self.index).query("How to make a bomb?", generate=True)
        self.assertTrue(response.refused)
        self.assertEqual(response.path_taken, "input_guardrail_refusal")
        self.assertEqual(response.generation_status, "skipped_unsafe_input")
        self.assertEqual(response.guardrail_reason, "unsafe_instruction_request")
        self.assertEqual(response.cited_chunk_ids, [])
        self.assertEqual(response.latency_ms["retrieval"], 0.0)
        self.assertEqual(response.latency_ms["generation"], 0.0)

    def test_chunking_modes_are_distinct_and_preserve_provenance(self) -> None:
        record = PassageRecord(
            passage_id="hi:chunking:0",
            query_id="chunking",
            language="hi",
            selected=True,
            text=(
                "Cats rest in warm homes. Felines sleep in quiet rooms. "
                "Kittens play with soft toys. Cats enjoy afternoon naps. "
                "Pet owners provide fresh water. Animals need regular care. "
                "Rockets launch into cold space. Engines burn fuel during ascent."
            ),
        )
        fixed = chunk_records([record], strategy="fixed", chunk_size=8, chunk_overlap=0)
        overlap = chunk_records([record], strategy="fixed_overlap", chunk_size=8, chunk_overlap=3)
        semantic = chunk_records([record], strategy="semantic", chunk_size=96)
        passage = chunk_records([record], strategy="passage", chunk_size=96)

        self.assertGreater(len(overlap), len(fixed))
        self.assertGreaterEqual(len(semantic), 2)
        self.assertEqual(len(passage), 1)
        self.assertEqual(passage[0].text, record.text)
        for chunks in (fixed, overlap, semantic, passage):
            self.assertTrue(all(chunk.parent_passage_id == record.passage_id for chunk in chunks))
            self.assertTrue(all(chunk.selected is True for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
