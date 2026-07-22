import httpx
import pytest
import respx

from indusmind.llm.providers import LLMError, LLMRouter, ProviderConfig, TaskType


def _openai_response(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture()
def router() -> LLMRouter:
    primary = ProviderConfig(name="qwen", base_url="https://primary.test/v1", api_key="k1", model="qwen-plus")
    fallback = ProviderConfig(name="deepseek", base_url="https://fallback.test/v1", api_key="k2", model="deepseek-chat")
    return LLMRouter({TaskType.FAST_RERANK: (primary, fallback)})


@pytest.mark.asyncio
@respx.mock
async def test_chat_uses_primary_when_healthy(router: LLMRouter):
    respx.post("https://primary.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_openai_response("hello from primary"))
    )
    result = await router.chat(TaskType.FAST_RERANK, [{"role": "user", "content": "hi"}])
    assert result == "hello from primary"


@pytest.mark.asyncio
@respx.mock
async def test_chat_falls_back_when_primary_fails(router: LLMRouter):
    respx.post("https://primary.test/v1/chat/completions").mock(return_value=httpx.Response(500))
    respx.post("https://fallback.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json=_openai_response("hello from fallback"))
    )
    result = await router.chat(TaskType.FAST_RERANK, [{"role": "user", "content": "hi"}])
    assert result == "hello from fallback"


@pytest.mark.asyncio
@respx.mock
async def test_chat_raises_when_both_fail(router: LLMRouter):
    respx.post("https://primary.test/v1/chat/completions").mock(return_value=httpx.Response(500))
    respx.post("https://fallback.test/v1/chat/completions").mock(return_value=httpx.Response(500))
    with pytest.raises(LLMError):
        await router.chat(TaskType.FAST_RERANK, [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_raises_when_missing_api_key():
    primary = ProviderConfig(name="qwen", base_url="https://primary.test/v1", api_key="", model="qwen-plus")
    fallback = ProviderConfig(name="deepseek", base_url="https://fallback.test/v1", api_key="", model="deepseek-chat")
    router = LLMRouter({TaskType.FAST_RERANK: (primary, fallback)})
    with pytest.raises(LLMError):
        await router.chat(TaskType.FAST_RERANK, [{"role": "user", "content": "hi"}])
