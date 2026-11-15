# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, UploadFile

from aperag.agent.sap_scenarios import CODE_SCENARIO, is_code_orchestration
from aperag.db.models import random_id
from aperag.db.ops import async_db_ops
from aperag.objectstore.base import get_async_object_store
from aperag.schema import view_models
from aperag.service.chat_collection_service import chat_collection_service
from aperag.service.document_service import document_service
from aperag.utils.utils import utc_now

logger = logging.getLogger(__name__)
CODE_SUFFIXES = {".abap", ".java"}
MAX_CODE_BYTES = 48 * 1024


def decode_source_code(data: bytes) -> str:
    if not data or len(data) > MAX_CODE_BYTES:
        raise ValueError("Code files must be nonempty and at most 48 KiB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Code files must be UTF-8") from exc
    if not text.strip() or any(ord(char) < 32 and char not in "\r\n\t" for char in text):
        raise ValueError("Code files must contain plain text")
    return text


class ChatDocumentService:
    """
    Chat document service for handling document uploads in chat sessions
    """

    def __init__(self):
        self.db_ops = async_db_ops

    async def upload_chat_document(self, chat_id: str, user_id: str, file: UploadFile) -> view_models.Document:
        """Upload chat document to user's chat collection"""
        original_filename = file.filename or "attachment"
        source_code = Path(original_filename).suffix.lower() in CODE_SUFFIXES
        chat = await self.db_ops.query_chat_for_user(user_id, chat_id)
        bot = await self.db_ops.query_bot(user_id, chat.bot_id) if chat else None
        if not bot:
            raise HTTPException(status_code=404, detail="Chat not found")
        orchestration = view_models.BotConfig.model_validate_json(bot.config).orchestration if bot.config else None
        if is_code_orchestration(orchestration) and not source_code:
            raise HTTPException(status_code=400, detail="The Code Agent accepts .abap or .java files")
        if source_code:
            if not orchestration or not any(s.enabled and s.category == CODE_SCENARIO for s in orchestration.skills):
                raise HTTPException(status_code=400, detail="This Agent does not accept ABAP or Java files")
            try:
                decode_source_code(await file.read(MAX_CODE_BYTES + 1))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            finally:
                await file.seek(0)

        # Get user's chat collection (should exist from registration)
        collection = await chat_collection_service.get_user_chat_collection(user_id)
        if not collection:
            # Create if missing (fallback)
            collection = await chat_collection_service.create_user_chat_collection(user_id)

        unique_filename = self._build_unique_filename(original_filename)
        file.filename = unique_filename

        # Prepare document metadata (without message_id initially)
        doc_metadata = {
            "chat_id": chat_id,
            "file_type": "chat_upload",
            "original_name": original_filename,
        }
        if source_code:
            doc_metadata["source_code"] = True

        # Use document service to create document
        documents = await document_service.create_documents(
            user_id, collection.id, [file], doc_metadata, ignore_duplicate=True, index_documents=not source_code
        )

        if not documents.items:
            raise HTTPException(status_code=500, detail="Failed to upload document")

        return documents.items[0]

    async def read_code_attachments(
        self, user_id: str, chat_id: str, files: list[view_models.File],
    ) -> list[dict[str, str]]:
        if len(files) != 1 or not files[0].id:
            raise ValueError("Select one code file")
        document = await self.db_ops.query_document_by_id(files[0].id)
        if not document or document.user != user_id:
            raise ValueError("Code attachment unavailable")
        metadata = json.loads(document.doc_metadata or "{}")
        suffix = Path(document.name).suffix.lower()
        if (
            suffix not in CODE_SUFFIXES
            or metadata.get("chat_id") != chat_id
            or metadata.get("file_type") != "chat_upload"
            or metadata.get("source_code") is not True
        ):
            raise ValueError("Code attachment unavailable")
        path = f"{document.object_store_base_path()}/original{suffix}"
        result = await get_async_object_store().get(path)
        if not result:
            raise ValueError("Code attachment unavailable")
        stream, _ = result
        content = bytearray()
        async for part in stream:
            content.extend(part)
            if len(content) > MAX_CODE_BYTES:
                raise ValueError("Code attachment too large")
        return [{"name": metadata.get("original_name") or document.name, "code": decode_source_code(bytes(content))}]

    @staticmethod
    def _build_unique_filename(filename: str) -> str:
        suffix = Path(filename).suffix
        stem = Path(filename).stem or "attachment"
        return f"{stem}-{random_id()}{suffix}"

    async def get_chat_document_by_id(
        self, chat_id: str, document_id: str, user_id: str
    ) -> Optional[view_models.Document]:
        """Get chat document by ID with chat ownership validation"""
        # Get user's chat collection
        collection = await chat_collection_service.get_user_chat_collection(user_id)
        if not collection:
            return None

        document = await self.db_ops.query_document_by_id(document_id)
        if not document or document.collection_id != collection.id:
            return None
        try:
            metadata = json.loads(document.doc_metadata or "{}")
        except ValueError:
            return None
        if metadata.get("file_type") != "chat_upload" or metadata.get("chat_id") != chat_id:
            return None
        return await document_service.get_document(user_id, collection.id, document_id)

    async def get_documents_metadata(self, chat_id: str, document_ids: List[str], user_id: str) -> List[Dict[str, Any]]:
        """Get metadata for documents to be stored in chat message"""
        if not document_ids:
            return []

        # Get user's chat collection
        collection = await chat_collection_service.get_user_chat_collection(user_id)
        if not collection:
            return []

        documents_metadata = []
        for document_id in document_ids:
            document = await self.db_ops.query_document_by_id(document_id)
            if not document or document.collection_id != collection.id:
                continue

            # Verify it's a chat document for this chat
            if document.doc_metadata:
                try:
                    metadata = json.loads(document.doc_metadata)
                    if metadata.get("file_type") == "chat_upload" and metadata.get("chat_id") == chat_id:
                        # Build file metadata for message storage
                        file_info = {
                            "id": document.id,
                            "name": document.name,
                            "previewUrl": f"/api/v1/collections/{collection.id}/documents/{document.id}/download",
                            "size": document.size,
                            "status": getattr(document.status, "value", document.status),
                            "created": document.gmt_created.isoformat(),
                            "updated": document.gmt_updated.isoformat(),
                        }
                        documents_metadata.append(file_info)
                except json.JSONDecodeError:
                    continue

        return documents_metadata

    async def associate_documents_with_message(
        self, chat_id: str, message_id: str, files: List[str], user: str
    ) -> List[Dict[str, Any]]:
        """Handle file metadata retrieval and document association for chat messages.

        Args:
            chat_id: The chat ID
            message_id: The message ID to associate documents with
            files: List of document IDs
            user: User ID

        Returns:
            List of file metadata dictionaries
        """
        if not files:
            return []

        result = []
        try:
            from aperag.service.chat_document_service import chat_document_service

            # Get document metadata for storing in the message
            result = await chat_document_service.get_documents_metadata(
                chat_id=chat_id, document_ids=files, user_id=user
            )
            # Associate documents with message
            await self._associate_documents_with_message(
                chat_id=chat_id, message_id=message_id, document_ids=files, user_id=user
            )
        except Exception as e:
            logger.warning(f"Failed to associate documents with message {message_id}: {e}")

        return result

    async def _associate_documents_with_message(
        self, chat_id: str, message_id: str, document_ids: List[str], user_id: str
    ) -> None:
        """Associate uploaded documents with a message when user sends the message"""
        # Get user's chat collection
        collection = await chat_collection_service.get_user_chat_collection(user_id)
        if not collection:
            return

        # Update each document's metadata to include message_id
        for document_id in document_ids:
            document = await self.db_ops.query_document_by_id(document_id)
            if not document or document.collection_id != collection.id:
                continue

            # Verify it's a chat document for this chat
            if document.doc_metadata:
                try:
                    metadata = json.loads(document.doc_metadata)
                    if metadata.get("file_type") == "chat_upload" and metadata.get("chat_id") == chat_id:
                        # Update metadata with message_id
                        metadata["message_id"] = message_id
                        metadata["updated_at"] = utc_now().isoformat()
                        await self.db_ops.update_document_by_id(
                            user=user_id,
                            collection_id=collection.id,
                            document_id=document.id,
                            metadata=json.dumps(metadata),
                        )
                        logger.info(f"Associated document {document_id} with message {message_id}")
                except json.JSONDecodeError:
                    continue


# Global service instance
chat_document_service = ChatDocumentService()
