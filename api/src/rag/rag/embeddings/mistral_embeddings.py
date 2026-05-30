from functools import lru_cache

from langchain_mistralai import MistralAIEmbeddings

from rag.config.settings import get_settings


@lru_cache
def get_embeddings() -> MistralAIEmbeddings:
    settings = get_settings()
    return MistralAIEmbeddings(
        model="mistral-embed",
        api_key=settings.mistral_api_key,
    )


async def embed_documents(texts: list[str]) -> list[list[float]]:
    return await get_embeddings().aembed_documents(texts)


async def embed_query(text: str) -> list[float]:
    return await get_embeddings().aembed_query(text)
