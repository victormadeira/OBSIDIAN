"""
Embedding Provider Interface — pluggable architecture for vector embeddings.

Supports:
  - LocalProvider: sentence-transformers (offline, no API key)
  - OpenAIProvider: text-embedding-3-small (higher quality, needs key)
  - OllamaProvider: local LLM embeddings via Ollama (offline, needs Ollama running)

The provider is selected via config. New providers implement BaseEmbeddingProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    """Interface that all embedding providers must implement."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts. More efficient than N single calls."""
        ...

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...

    @abstractmethod
    def get_model_name(self) -> str:
        """Return identifier for the model being used."""
        ...


class LocalProvider(BaseEmbeddingProvider):
    """
    Offline embeddings using sentence-transformers.
    Default model: all-MiniLM-L6-v2 (384 dimensions, ~80MB, fast).
    No API key required. Works 100% offline.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._dimension = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            # Get dimension from a test embedding
            test = self._model.encode(["test"])
            self._dimension = len(test[0])
            logger.info(f"Model loaded. Dimension: {self._dimension}")
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )

    def embed_text(self, text: str) -> list[float]:
        self._load_model()
        embedding = self._model.encode([text], show_progress_bar=False)
        return embedding[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        if not texts:
            return []
        embeddings = self._model.encode(texts, show_progress_bar=False, batch_size=32)
        return [e.tolist() for e in embeddings]

    def get_dimension(self) -> int:
        self._load_model()
        return self._dimension

    def get_model_name(self) -> str:
        return f"local/{self._model_name}"


class OpenAIProvider(BaseEmbeddingProvider):
    """
    Embeddings via OpenAI API (text-embedding-3-small).
    Requires OPENAI_API_KEY environment variable.
    1536 dimensions, high quality.
    """

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: Optional[str] = None):
        self._model_name = model_name
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None
        if not self._api_key:
            raise RuntimeError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key to the provider."
            )

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
            return self._client
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

    def embed_text(self, text: str) -> list[float]:
        client = self._get_client()
        response = client.embeddings.create(input=[text], model=self._model_name)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        # OpenAI supports batch natively, max 2048 inputs
        all_embeddings = []
        for i in range(0, len(texts), 2048):
            batch = texts[i:i + 2048]
            response = client.embeddings.create(input=batch, model=self._model_name)
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings

    def get_dimension(self) -> int:
        dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dims.get(self._model_name, 1536)

    def get_model_name(self) -> str:
        return f"openai/{self._model_name}"


class OllamaProvider(BaseEmbeddingProvider):
    """
    Embeddings via local Ollama server.
    Requires Ollama running locally with an embedding model pulled.
    Default model: nomic-embed-text (768 dimensions).
    """

    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self._model_name = model_name
        self._base_url = base_url
        self._dimension = None

    def _request(self, texts: list[str]) -> list[list[float]]:
        import urllib.request
        import json

        results = []
        for text in texts:
            payload = json.dumps({"model": self._model_name, "prompt": text}).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/embeddings",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                results.append(data["embedding"])

        if results and self._dimension is None:
            self._dimension = len(results[0])
        return results

    def embed_text(self, text: str) -> list[float]:
        return self._request([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._request(texts)

    def get_dimension(self) -> int:
        if self._dimension is None:
            # Do a probe
            self.embed_text("test")
        return self._dimension or 768

    def get_model_name(self) -> str:
        return f"ollama/{self._model_name}"


def create_provider(
    provider_type: str = "local",
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> BaseEmbeddingProvider:
    """Factory function. Creates the appropriate provider based on config."""

    if provider_type == "local":
        return LocalProvider(model_name=model_name or "all-MiniLM-L6-v2")
    elif provider_type == "openai":
        return OpenAIProvider(model_name=model_name or "text-embedding-3-small", api_key=api_key)
    elif provider_type == "ollama":
        return OllamaProvider(
            model_name=model_name or "nomic-embed-text",
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider_type}")
