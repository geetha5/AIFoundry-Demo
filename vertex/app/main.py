"""
Tiny RAG service backed by Azure AI Foundry.

Retrieves the most relevant chunks from the local index (built by
ingest.py) and asks the deployed chat model to answer using only that
context. Exposed as a small FastAPI app so it can be smoke-tested with a
plain HTTP call after each deploy.

Run locally:
    uvicorn app.main:app --reload

Endpoints:
    GET  /health   -> liveness check used by the CI/CD smoke test
    POST /query    -> {"question": "..."} -> {"answer": "...", "sources": [...]}
"""
import os
import json
import math
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel
from openai import AzureOpenAI

INDEX_PATH = Path(__file__).parent / "index.json"
TOP_K = 3

app = FastAPI(title="vertex-rag-demo")


def get_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=os.environ["AZURE_AI_FOUNDRY_API_KEY"],
        azure_endpoint=os.environ["AZURE_AI_FOUNDRY_ENDPOINT"],
        api_version="2024-10-21",
    )


def load_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    return json.loads(INDEX_PATH.read_text())


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(question: str, client: AzureOpenAI, index: list[dict]) -> list[dict]:
    embedding_deployment = os.environ["AZURE_EMBEDDING_DEPLOYMENT"]
    q_emb = client.embeddings.create(
        model=embedding_deployment, input=question
    ).data[0].embedding

    scored = [
        {**record, "score": cosine_similarity(q_emb, record["embedding"])}
        for record in index
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:TOP_K]


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    client = get_client()
    chat_deployment = os.environ["AZURE_CHAT_DEPLOYMENT"]
    index = load_index()

    top_chunks = retrieve(req.question, client, index)
    context = "\n\n".join(c["text"] for c in top_chunks)
    sources = sorted({c["source"] for c in top_chunks})

    completion = client.chat.completions.create(
        model=chat_deployment,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer only using the provided context. "
                    "If the context does not contain the answer, say you "
                    "don't have that information."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {req.question}",
            },
        ],
        temperature=0.1,
    )

    return QueryResponse(
        answer=completion.choices[0].message.content,
        sources=sources,
    )
