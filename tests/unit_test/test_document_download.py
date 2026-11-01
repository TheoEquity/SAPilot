"""Download regressions using the real service, SQL query and streaming response.

An isolated SQLite document table replaces the application database; only object
storage is stubbed. These tests do not access application data or model APIs.
"""

import asyncio
import json
from datetime import datetime, timezone
from email.message import Message
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import aperag.service.document_service as document_module
from aperag.db.models import Document, DocumentStatus
from aperag.exceptions import DocumentNotFoundException

CONTENT = b"original file bytes\x00\xff"


@pytest.fixture
def download(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Document.__table__.create(engine)
    with Session(engine) as session:
        document = Document(
            id="doc-download",
            name="original.pdf",
            user="owner",
            collection_id="collection-download",
            status=DocumentStatus.COMPLETE,
            size=len(CONTENT),
            doc_metadata=json.dumps({"object_path": "original-object"}),
        )
        session.add(document)
        session.commit()

        async def execute(statement):
            return session.execute(statement)

        async def execute_query(operation):
            return await operation(SimpleNamespace(execute=execute))

        async def stream():
            yield CONTENT[:5]
            yield CONTENT[5:]

        async def get_object(path):
            assert path == "original-object"
            return stream(), len(CONTENT)

        store = SimpleNamespace(get=AsyncMock(side_effect=get_object))
        monkeypatch.setattr(document_module, "get_async_object_store", lambda: store)
        service = document_module.DocumentService()
        service.db_ops = SimpleNamespace(_execute_query=execute_query)

        def call(user="owner", collection="collection-download", document_id="doc-download"):
            return asyncio.run(service.download_document(user, collection, document_id))

        yield SimpleNamespace(document=document, session=session, store=store, call=call)
    engine.dispose()


@pytest.mark.parametrize(
    "filename, content_type",
    [
        ("SAP运维规范.pdf", "application/pdf"),
        ("test_download.txt", "text/plain"),
        ("SAP report 100%.pdf", "application/pdf"),
        ('report; "final".pdf', "application/pdf"),
        ("équipe's report.pdf", "application/pdf"),
        ("folder\\report.pdf", "application/pdf"),
        ("report\r\nX-Injected: yes.pdf", "application/pdf"),
        ("original.unknownextension", "application/octet-stream"),
    ],
)
def test_download_preserves_filename_headers_and_original_stream(download, filename, content_type):
    download.document.name = filename
    download.session.commit()
    response = download.call()
    assert response.status_code == 200
    assert response.headers["content-type"] == content_type
    assert response.headers["content-length"] == str(len(CONTENT))
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition
    assert "\\" not in disposition
    assert disposition.count('"') in (0, 2)
    message = Message()
    message["content-disposition"] = disposition
    assert message.get_content_disposition() == "attachment"
    assert message.get_filename() == filename

    async def read_stream():
        return b"".join([chunk async for chunk in response.body_iterator])

    assert asyncio.run(read_stream()) == CONTENT


def test_download_allows_staged_documents(download):
    download.document.status = DocumentStatus.UPLOADED
    download.session.commit()
    assert download.call().status_code == 200


@pytest.mark.parametrize(
    "kwargs, deleted",
    [
        ({"user": "another-user"}, False),
        ({"collection": "another-collection"}, False),
        ({"document_id": "missing-document"}, False),
        ({}, True),
    ],
)
def test_download_hides_inaccessible_or_deleted_documents(download, kwargs, deleted):
    if deleted:
        download.document.gmt_deleted = datetime.now(timezone.utc)
        download.session.commit()
    with pytest.raises(DocumentNotFoundException) as error:
        download.call(**kwargs)
    assert error.value.http_status == 404
    download.store.get.assert_not_called()


@pytest.mark.parametrize("status", [DocumentStatus.EXPIRED, DocumentStatus.DELETED])
def test_download_rejects_unavailable_document_status(download, status):
    download.document.status = status
    download.session.commit()
    with pytest.raises(HTTPException) as error:
        download.call()
    assert error.value.status_code == 400
    download.store.get.assert_not_called()


@pytest.mark.parametrize("metadata, expected_status", [(None, 404), ("{}", 404), ("invalid-json", 500)])
def test_download_rejects_missing_or_corrupt_metadata(download, metadata, expected_status):
    download.document.doc_metadata = metadata
    download.session.commit()
    with pytest.raises(HTTPException) as error:
        download.call()
    assert error.value.status_code == expected_status
    download.store.get.assert_not_called()


def test_download_reports_object_storage_failure(download):
    download.store.get.side_effect = OSError("storage unavailable")
    with pytest.raises(HTTPException) as error:
        download.call()
    assert error.value.status_code == 500


def test_download_reports_missing_storage_object(download):
    download.store.get.side_effect = None
    download.store.get.return_value = None
    with pytest.raises(HTTPException) as error:
        download.call()
    assert error.value.status_code == 404
