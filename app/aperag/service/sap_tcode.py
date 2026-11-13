"""Read transaction-code evidence from source tables."""

import asyncio
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from math import hypot
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

_TRANSACTION_CODE = re.compile(r"(?:/[A-Z0-9_]+/)?[A-Z0-9_]+(?:[.-][A-Z0-9_]+)*", re.IGNORECASE | re.ASCII)
_CODE_IN_QUERY = re.compile(
    rf"(?<![A-Z0-9_/])(?:/n)?({_TRANSACTION_CODE.pattern})(?![A-Z0-9_/]|[.-][A-Z0-9_])",
    re.IGNORECASE | re.ASCII,
)
_CODE_HEADERS = {"tcode", "transactioncode", "事务码", "事务代码", "操作码"}
_PURPOSE_HEADERS = {"功能描述", "功能", "用途", "描述", "description", "purpose"}
_MARKDOWN = MarkdownIt().enable("table")
_LOOKUP_WORDS = re.compile(
    r"事务代码|事务码|交易码|操作码|t[ -]?codes?|有哪些|哪些|相关|可以用|可用|能用|请问",
    re.I,
)
_SYSTEM_CONTEXT = re.compile(r"\b(?:sap|gui|erp|s4hana|hana|ecc)\b", re.I)
_ENGLISH_LOOKUP = re.compile(
    r"^\s*(?:what|which)\s+(?:are\s+the\s+)?(?:transaction\s+codes?|t[ -]?codes?)"
    r"(?:\s+(?:can be used (?:for|to)|are used (?:for|to)|help|are available for))?\s*",
    re.I,
)
_REVERSE_QUESTION = re.compile(
    r"有哪些|哪些|什么(?:事务码|事务代码|交易码|操作码)"
    r"|\b(?:what|which)\s+(?:are\s+the\s+)?(?:transaction\s+codes?|t[ -]?codes?)\b",
    re.I,
)
_EXPLICIT_LOOKUP = re.compile(
    rf"(?:查(?:找|询|一下)?\s+|\b(?:what is|look up|what does|how (?:do|can) i use)\s+)"
    rf"(?:/n)?({_TRANSACTION_CODE.pattern})",
    re.I,
)
_TCODE_QUERY_WORDS = {
    "SAP",
    "CODE",
    "ERP",
    "ABAP",
    "JAVA",
    "TCODE",
    "TCODES",
    "T-CODE",
    "T-CODES",
    "GUI",
    "ECC",
    "HANA",
    "S4HANA",
    "FICO",
}
_PURPOSE_TRANSLATIONS = {
    "authorization management": "权限管理",
    "authorisation management": "权限管理",
    "purchase order": "采购订单",
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TCodeRow:
    code: str
    purpose: str
    section: str
    line: int


def _code_value(value: str) -> bool:
    return bool(2 <= len(value) <= 20 and _TRANSACTION_CODE.fullmatch(value) and re.search(r"[A-Z]", value, re.I))


def match_exact_tcode(query: str) -> str | None:
    """Recognize an unambiguous code in an ordinary lookup question."""
    if _REVERSE_QUESTION.search(query):
        return None
    tokens = [
        token
        for token in _CODE_IN_QUERY.findall(query)
        if _code_value(token) and token.upper() not in _TCODE_QUERY_WORDS
    ]
    candidates = {token.upper() for token in tokens if re.search(r"[0-9/.-]", token)}
    if not candidates and (explicit := _EXPLICIT_LOOKUP.search(query)):
        token = explicit.group(1)
        if token in tokens:
            candidates = {token.upper()}
    if not candidates:
        candidates = {token.upper() for token in tokens if token.isupper() and len(token) >= 3}
    if (
        not candidates
        and len(tokens) == 1
        and (_code_value(query.strip()) or re.search(r"是什么|干什么|用途|做什么", query))
    ):
        candidates = {tokens[0].upper()}
    return next(iter(candidates)) if len(candidates) == 1 else None


def _inline_text(token: Token) -> str:
    return "".join(
        " " if child.type in {"softbreak", "hardbreak"} else child.content
        for child in token.children or []
        if child.type in {"text", "code_inline", "softbreak", "hardbreak"}
    ).strip()


def extract_tcode_rows(markdown: str) -> list[TCodeRow]:
    """Read rows only from tables with named transaction-code and purpose columns."""
    section = ""
    header = False
    code_column = purpose_column = None
    cells: list[str] = []
    rows: list[TCodeRow] = []
    line = 0
    tokens = _MARKDOWN.parse(markdown)
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            section = _inline_text(tokens[index + 1])
        elif token.type == "table_open":
            code_column = purpose_column = None
        elif token.type == "thead_open":
            header = True
        elif token.type == "thead_close":
            header = False
        elif token.type == "tr_open":
            cells = []
            line = token.map[0] + 1 if token.map else 0
        elif token.type == "inline" and index and tokens[index - 1].type in {"th_open", "td_open"}:
            cells.append(_inline_text(token))
        elif token.type == "tr_close" and (header or code_column is None or purpose_column is None):
            # Word tables can arrive with a blank Markdown header, followed
            # by the actual column names as the first body row.
            names = [re.sub(r"[\s_-]", "", cell.casefold()) for cell in cells]
            code_column = next((i for i, name in enumerate(names) if name in _CODE_HEADERS), None)
            purpose_column = next((i for i, name in enumerate(names) if name in _PURPOSE_HEADERS), None)
        elif token.type == "tr_close" and code_column is not None and purpose_column is not None:
            if len(cells) <= max(code_column, purpose_column):
                continue
            code, purpose = cells[code_column].upper(), cells[purpose_column]
            if _code_value(code) and purpose:
                rows.append(TCodeRow(code, purpose, section, line))
    return rows


def _normalize_evidence(text: str) -> str:
    return re.sub(r"[^\w/]", "", text.casefold())


def _purpose_terms(query: str) -> set[str]:
    query = _SYSTEM_CONTEXT.sub(" ", _LOOKUP_WORDS.sub(" ", query))
    query = re.sub(
        r"\b(?:what|which|transaction|codes?|are|for|can|be|used|to|do|i|in|on|the|and|with|of|any|some|help)\b",
        " ",
        query,
        flags=re.I,
    )
    terms = set()
    query = re.sub(r"查找|查询|查一下|怎么|用什么|使用", " ", query)
    for phrase, translated in _PURPOSE_TRANSLATIONS.items():
        query = re.sub(rf"\b{phrase}s?\b", translated, query, flags=re.I)
    for word in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]{2,}", query.casefold()):
        if re.fullmatch(r"[\u3400-\u9fff]{2,}", word):
            if len(word) <= 4:
                terms.add(word)
            else:
                terms.update(word[index : index + 3] for index in range(len(word) - 2))
        elif len(word) >= 3:
            terms.add(word)
    return terms


def _purpose_overlap(terms: set[str], text: str) -> int:
    words = set(re.findall(r"[a-z0-9]+", text))
    return sum(term in words if term.isascii() else term in text for term in terms)


def _score_purposes(collection, query: str, purposes: list[str]) -> list[float]:
    from aperag.llm.embed.base_embedding import get_collection_embedding_service_sync

    model, _ = get_collection_embedding_service_sync(collection)
    query_vector = model.embed_query(query)
    purpose_vectors = model.embed_documents(purposes)
    query_norm = hypot(*query_vector)
    scores = []
    for vector in purpose_vectors:
        norm = query_norm * hypot(*vector)
        scores.append(sum(a * b for a, b in zip(query_vector, vector)) / norm if norm else 0.0)
    return scores


async def lookup_tcodes(user: str, collection_ids: Sequence[str], query: str) -> tuple[str, list[dict[str, Any]]]:
    """Recall indexed chunks and confirm each transaction against its original table."""
    from aperag.db.models import DocumentStatus
    from aperag.db.ops import async_db_ops
    from aperag.flow.runners.fulltext_search import FulltextSearchRepository, FulltextSearchService
    from aperag.flow.runners.vector_search import VectorSearchRepository, VectorSearchService
    from aperag.service.document_service import document_service

    code = match_exact_tcode(query)
    purpose_query = _ENGLISH_LOOKUP.sub("", _SYSTEM_CONTEXT.sub(" ", query).strip(" :"))
    purpose_query = " ".join(_LOOKUP_WORDS.sub(" ", purpose_query).strip(" ？?。:").split())
    if not collection_ids or not (code or purpose_query):
        return "请提供要查询的完整事务码或操作目的，并确认已配置事务码资料。", []

    fulltext = FulltextSearchService(FulltextSearchRepository())
    vector = VectorSearchService(VectorSearchRepository())
    hits = []
    for collection_id in dict.fromkeys(collection_ids):
        hits.extend(
            (collection_id, hit)
            for hit in await fulltext.execute_fulltext_search(
                user, code or purpose_query, 10, [collection_id], [code] if code else [purpose_query]
            )
        )
        if code is None:
            hits.extend(
                (collection_id, hit)
                for hit in await vector.execute_vector_search(user, purpose_query, 10, 0.2, [collection_id])
            )

    sources = {}
    ranked = {}
    vector_rows = {}
    terms = _purpose_terms(query)
    for rank, (collection_id, hit) in enumerate(hits):
        metadata = hit.metadata or {}
        document_id = metadata.get("document_id") or metadata.get("doc_id")
        if not document_id:
            continue
        key = (collection_id, document_id)
        if key not in sources:
            document = await async_db_ops.query_document(user, collection_id, document_id)
            sources[key] = None
            if document and document.status == DocumentStatus.COMPLETE and document.gmt_deleted is None:
                preview = await document_service.get_document_preview(user, collection_id, document_id)
                sources[key] = (preview.doc_filename, extract_tcode_rows(preview.markdown_content or ""))
        if not sources[key]:
            continue
        source, rows = sources[key]
        chunk = _normalize_evidence(hit.text or "")
        for row in rows:
            if code and row.code != code:
                continue
            description = _normalize_evidence(row.purpose)
            if not description or _normalize_evidence(row.code) + description not in chunk:
                continue
            # A chunk can contain several rows. Prefer the matching purpose
            # independently of the score for the surrounding chunk.
            row_text = f"{row.section} {row.purpose}".casefold()
            overlap = _purpose_overlap(terms, row_text)
            identity = (key, row.line)
            if code or overlap:
                ranked.setdefault(identity, ((-overlap, rank), row, source, key))
            if not code and metadata.get("recall_type") == "vector_search":
                vector_rows.setdefault(identity, (row, source, key))

    # Chunk similarity cannot tell which of its rows describes the intended
    # operation. Check the recalled rows individually when wording differs.
    if not code and not ranked:
        for collection_id in dict.fromkeys(collection_ids):
            candidates = [value for value in vector_rows.values() if value[2][0] == collection_id][:60]
            if not candidates:
                continue
            try:
                collection = await async_db_ops.query_collection(user, collection_id)
                scores = (
                    await asyncio.to_thread(
                        _score_purposes,
                        collection,
                        purpose_query,
                        [f"{row.code} {row.purpose}" for row, _, _ in candidates],
                    )
                    if collection
                    else []
                )
            except Exception:
                logger.warning(
                    "Transaction purpose ranking unavailable for collection %s", collection_id, exc_info=True
                )
                continue
            threshold = max(0.50, max(scores, default=0) * 0.89)
            for rank, (score, (row, source, key)) in enumerate(zip(scores, candidates)):
                if score >= threshold:
                    ranked[(key, row.line)] = ((-score, rank), row, source, key)

    ordered = sorted(ranked.values(), key=lambda candidate: candidate[0])
    if not ordered:
        return "当前资料中未检索到与该事务码或操作目的相符的条目。", []

    answer = []
    references = []
    for _, row, source, (collection_id, document_id) in ordered[:15]:
        location = f"{source} · {row.section}" if row.section else source
        evidence = f"{row.code} — {row.purpose}"
        answer.append(f"- **{row.code}**：{row.purpose}（{location}，解析文本第 {row.line} 行）")
        references.append(
            {
                "text": evidence,
                "metadata": {
                    "collection_id": collection_id,
                    "document_id": document_id,
                    "document_source": source,
                    "source": source,
                    "title": row.section,
                    "tcode": row.code,
                    "source_line": row.line,
                },
            }
        )
    return "\n".join(answer), references
