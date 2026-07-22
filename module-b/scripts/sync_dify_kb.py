#!/usr/bin/env python3
"""把本地叙述性知识（案例库 + 设备手册 chunk）同步到 Dify 知识库。

按 `.cursor/rules/tech-stack.mdc` 的分工：只同步"叙述文本"，FMEA / 工单 / 特征
元信息仍留在本地结构化文件，不进这个脚本。

用法：
    export DIFY_BASE_URL=https://api.dify.ai/v1        # 或自建实例地址
    export DIFY_DATASET_API_KEY=dataset-xxxx           # Dify 知识库 API Key
    export DIFY_CASES_DATASET_ID=xxxxxxxx-...          # 案例库 dataset_id
    export DIFY_MANUALS_DATASET_ID=xxxxxxxx-...        # 手册库 dataset_id
    python scripts/sync_dify_kb.py [--dry-run] [--only cases|manuals]

每条案例/chunk 上传时会在正文第一行写入 `case_id: xxx` / `chunk_id: xxx`，
`indusmind.rag.hybrid_search` 检索命中后据此回查本地结构化字段
（见 knowledge/cases/*.json、knowledge/manuals/chunks/*.json）。
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from indusmind.knowledge import default_store
from indusmind.rag.dify_client import DifyClient, DifyClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("sync_dify_kb")


def case_to_text(case: dict) -> str:
    """`case_to_text()`，附加 case_id 首行方便回查。"""
    symptoms = ", ".join(
        f"{s['feature']}({'↑' if s['direction'] == 'high' else '↓'})" for s in case.get("symptoms", [])
    )
    body = (
        f"设备 {case.get('device_model')} 发生 {case.get('anomaly_type')}。"
        f"征兆: {symptoms}。"
        f"根因: {case.get('root_cause')}。"
        f"机理: {case.get('mechanism')}"
    )
    return f"case_id: {case['case_id']}\n{body}"


def chunk_to_text(chunk: dict) -> str:
    header = f"chunk_id: {chunk['chunk_id']}\n[{chunk.get('device_model', '')} / {chunk.get('section', '')}]\n"
    return header + chunk.get("content", "")


async def sync_cases(client: DifyClient, dataset_id: str, dry_run: bool) -> int:
    cases = default_store.cases()
    for case in cases:
        text = case_to_text(case)
        if dry_run:
            logger.info("[dry-run] cases 文档: %s (%d 字)", case["case_id"], len(text))
            continue
        await client.upsert_document_by_text(dataset_id, name=case["case_id"], text=text)
        logger.info("已同步案例（创建或更新）: %s", case["case_id"])
    return len(cases)


async def sync_manuals(client: DifyClient, dataset_id: str, dry_run: bool) -> int:
    chunks = default_store.manual_chunks()
    for chunk in chunks:
        text = chunk_to_text(chunk)
        if dry_run:
            logger.info("[dry-run] manuals 文档: %s (%d 字)", chunk["chunk_id"], len(text))
            continue
        await client.upsert_document_by_text(dataset_id, name=chunk["chunk_id"], text=text)
        logger.info("已同步手册 chunk（创建或更新）: %s", chunk["chunk_id"])
    return len(chunks)


async def main_async(args: argparse.Namespace) -> int:
    client = DifyClient()

    if not client.api_key and not args.dry_run:
        logger.error("缺少 DIFY_DATASET_API_KEY，无法上传（可加 --dry-run 先预览）")
        return 1

    total = 0
    if args.only in (None, "cases"):
        cases_dataset_id = os.environ.get("DIFY_CASES_DATASET_ID")
        if not cases_dataset_id and not args.dry_run:
            logger.error("缺少 DIFY_CASES_DATASET_ID，跳过案例库同步")
        else:
            total += await sync_cases(client, cases_dataset_id or "dry-run-dataset", args.dry_run)

    if args.only in (None, "manuals"):
        manuals_dataset_id = os.environ.get("DIFY_MANUALS_DATASET_ID")
        if not manuals_dataset_id and not args.dry_run:
            logger.error("缺少 DIFY_MANUALS_DATASET_ID，跳过手册库同步")
        else:
            total += await sync_manuals(client, manuals_dataset_id or "dry-run-dataset", args.dry_run)

    logger.info("完成，共处理 %d 条文档", total)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只打印将上传的内容，不实际调用 Dify API")
    parser.add_argument("--only", choices=["cases", "manuals"], default=None, help="只同步案例库或手册库")
    args = parser.parse_args()
    try:
        exit_code = asyncio.run(main_async(args))
    except DifyClientError as exc:
        logger.error("Dify 配置错误：%s", exc)
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
