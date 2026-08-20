"""Verify that the selected local Indic sentence-embedding model can load."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

MODEL_NAME = "krutrim-ai-labs/Vyakyarth"


def main() -> None:
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vector = model.encode(["कॉर्पोरेशन क्या है?"], normalize_embeddings=True, show_progress_bar=False)
    print(f"model={MODEL_NAME}")
    print(f"dimensions={len(vector[0])}")


if __name__ == "__main__":
    main()
