"""Hugging Face Spaces entrypoint for Contextline."""
import os
import sys

# Default to Hugging Face Space port 7860 if PORT environment variable is not explicitly provided
if "PORT" not in os.environ:
    os.environ["PORT"] = "7860"

from src.serve import main

if __name__ == "__main__":
    main()
