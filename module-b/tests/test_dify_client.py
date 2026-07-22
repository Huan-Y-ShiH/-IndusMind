import httpx
import pytest
import respx

from indusmind.rag.dify_client import DifyClient, DifyClientError


@pytest.mark.asyncio
@respx.mock
async def test_retrieve_parses_records():
    respx.post("https://dify.test/v1/datasets/ds/retrieve").mock(
        return_value=httpx.Response(
            200,
            json={
                "records": [
                    {
                        "segment": {
                            "id": "seg-1",
                            "document_id": "doc-1",
                            "content": "case_id: case-1\n正文",
                            "document": {"name": "case-1"},
                        },
                        "score": 0.91,
                    }
                ]
            },
        )
    )
    client = DifyClient(base_url="https://dify.test/v1", api_key="test", max_retries=0)
    records = await client.retrieve("ds", "query")
    assert records[0].document_name == "case-1"
    assert records[0].score == 0.91


@pytest.mark.asyncio
@respx.mock
async def test_upsert_updates_existing_document():
    respx.get("https://dify.test/v1/datasets/ds/documents").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "doc-1", "name": "case-1"}]})
    )
    update = respx.post(
        "https://dify.test/v1/datasets/ds/documents/doc-1/update-by-text"
    ).mock(return_value=httpx.Response(200, json={"document": {"id": "doc-1"}}))
    client = DifyClient(base_url="https://dify.test/v1", api_key="test", max_retries=0)
    await client.upsert_document_by_text("ds", "case-1", "正文")
    assert update.called


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_is_not_retried():
    route = respx.post("https://dify.test/v1/datasets/ds/retrieve").mock(
        return_value=httpx.Response(401, json={"message": "unauthorized"})
    )
    client = DifyClient(base_url="https://dify.test/v1", api_key="bad", max_retries=2)
    with pytest.raises(DifyClientError, match="鉴权失败"):
        await client.retrieve("ds", "query")
    assert route.call_count == 1
