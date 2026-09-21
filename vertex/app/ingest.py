"""
Builds a simple local vector index over the /docs folder using
Azure AI Foundry's embeddings endpoint. Run this once (or whenever docs
change) before starting the app.

Usage:
    python app/ingest.py
"""
import os
import json
import glob
from pathlib import Path

from openai import AzureOpenAI

DOCS_DIR = Path(__file__).parent.parent / "docs"
INDEX_PATH = Path(__file__).parent / "index.json"

CHUNK_SIZE = 500  # characters per chunk, kept small since docs are tiny


def get_client() -> AzureOpenAI:
    """Azure AI Foundry exposes an OpenAI-compatible endpoint, so the
    standard OpenAI SDK works against it directly."""
    return AzureOpenAI(
        api_key=os.environ["AZURE_AI_FOUNDRY_API_KEY"],
        azure_endpoint=os.environ["AZURE_AI_FOUNDRY_ENDPOINT"],
        api_version="2024-10-21",
    )


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    words = text.split()
    chunks, current = [], []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= size:
            chunks.append(" ".join(current))
            current, current_len = [], 0
    if current:
        chunks.append(" ".join(current))
    return chunks


def main() -> None:
    client = get_client()
    embedding_deployment = os.environ["AZURE_EMBEDDING_DEPLOYMENT"]

    records = []
    for filepath in sorted(glob.glob(str(DOCS_DIR / "*.txt"))):
        text = Path(filepath).read_text()
        for i, chunk in enumerate(chunk_text(text)):
            resp = client.embeddings.create(
                model=embedding_deployment,
                input=chunk,
            )
            records.append(
                {
                    "source": os.path.basename(filepath),
                    "chunk_id": i,
                    "text": chunk,
                    "embedding": resp.data[0].embedding,
                }
            )
            print(f"embedded {os.path.basename(filepath)} chunk {i}")

    INDEX_PATH.write_text(json.dumps(records))
    print(f"wrote {len(records)} chunks to {INDEX_PATH}")


if __name__ == "__main__":
    main()
