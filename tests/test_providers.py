from pathlib import Path
import unittest

from src.chunking import chunk_records
from src.data import load_jsonl
from src.pipeline import TextRAGPipeline
from src.providers import OpenAICompatibleGenerator, SarvamTranscriber
from src.retrieval import HybridIndex


FIXTURE = Path("tests/fixtures/mini_msmarco_xi.jsonl")


class ProviderIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        chunks = chunk_records(load_jsonl(FIXTURE), strategy="sentence", chunk_size=32)
        self.index = HybridIndex(chunks, dimensions=64)

    def test_provider_configuration_is_reported_without_exposing_keys(self) -> None:
        self.assertFalse(SarvamTranscriber(api_key=None).configured)
        self.assertFalse(OpenAICompatibleGenerator(None, "https://api.openai.com/v1", "test-model").configured)

    def test_unconfigured_generation_fails_closed(self) -> None:
        generator = OpenAICompatibleGenerator(None, "https://api.openai.com/v1", "test-model")
        response = TextRAGPipeline(self.index, generator=generator).query(
            "What is BM25?", generate=True
        )
        self.assertTrue(response.refused)
        self.assertEqual(response.generation_status, "unavailable")
        self.assertEqual(response.cited_chunk_ids, [])
        self.assertEqual(response.path_taken, "generation_unavailable")


if __name__ == "__main__":
    unittest.main()
