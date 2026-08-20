import unittest

from src.languages import DEFAULT_LANGUAGE_ORDER, require_supported_language


class LanguageConfigurationTests(unittest.TestCase):
    def test_competition_language_scope_is_hindi_kannada_telugu(self) -> None:
        self.assertEqual(DEFAULT_LANGUAGE_ORDER, ("hi", "kn", "te"))
        self.assertEqual(require_supported_language("hi").display_name, "Hindi")
        self.assertEqual(require_supported_language("kn").stt_code, "kn-IN")
        self.assertEqual(require_supported_language("te").validation_parquet, "validation/telval.parquet")

    def test_unsupported_language_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            require_supported_language("ta")


if __name__ == "__main__":
    unittest.main()
