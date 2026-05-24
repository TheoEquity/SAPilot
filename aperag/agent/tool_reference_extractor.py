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

"""Tool call reference extractor for agent conversations."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .exceptions import (
    JSONParsingError,
    ToolReferenceExtractionError,
    handle_agent_error,
    safe_json_parse,
)

logger = logging.getLogger(__name__)


def _extract_tool_call_references_from_messages(history_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    references = []

    if not history_messages:
        logger.debug("No history messages found in memory")
        return references

    target_faq_ids = _extract_answer_faq_ids(history_messages)

    for message in history_messages:
        # Check if message has tool calls (message is a dict)
        if isinstance(message, dict) and message.get("role") == "assistant" and message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                try:
                    # Debug: log the actual structure
                    logger.debug(f"Tool call structure: {tool_call}, type: {type(tool_call)}")

                    # Process tool call information
                    # Handle different tool call structures (dict vs object)
                    tool_name = "unknown_tool"
                    tool_args = "{}"
                    tool_call_id = ""

                    # Handle OpenAI ChatCompletionMessageToolCall objects
                    if hasattr(tool_call, "id"):
                        tool_call_id = tool_call.id
                        if hasattr(tool_call, "function"):
                            tool_name = (
                                tool_call.function.name if hasattr(tool_call.function, "name") else "unknown_tool"
                            )
                            tool_args = (
                                tool_call.function.arguments if hasattr(tool_call.function, "arguments") else "{}"
                            )
                    # Handle dictionary format
                    elif isinstance(tool_call, dict):
                        tool_call_id = tool_call.get("id", "")
                        if "function" in tool_call:
                            tool_name = tool_call["function"].get("name", "unknown_tool")
                            tool_args = tool_call["function"].get("arguments", "{}")
                        elif "name" in tool_call:
                            tool_name = tool_call.get("name", "unknown_tool")
                            tool_args = tool_call.get("arguments", "{}")
                        elif "type" in tool_call and tool_call["type"] == "function":
                            tool_name = tool_call.get("function", {}).get("name", "unknown_tool")
                            tool_args = tool_call.get("function", {}).get("arguments", "{}")

                    logger.debug(
                        f"Extracted tool_name: {tool_name}, tool_args: {tool_args}, tool_call_id: {tool_call_id}"
                    )

                    # Parse tool arguments using safe parsing
                    try:
                        args_dict = (
                            safe_json_parse(tool_args, f"tool_args_{tool_name}")
                            if isinstance(tool_args, str)
                            else tool_args
                        )
                    except JSONParsingError:
                        logger.warning(f"Failed to parse tool arguments for {tool_name}, using raw args")
                        args_dict = {"raw_args": tool_args}

                    # Find corresponding tool result message
                    tool_result = _find_tool_result(history_messages, tool_call_id)

                    if tool_result:
                        # Format reference based on tool type
                        ref = None
                        try:
                            if tool_name == "aperag_search_collection":
                                ref = _format_search_reference(tool_result, args_dict, target_faq_ids)
                            elif tool_name == "aperag_search_chat_files":
                                ref = _format_search_chat_files_reference(tool_result, args_dict, target_faq_ids)
                            elif tool_name == "aperag_list_collections":
                                ref = _format_list_reference(tool_result, args_dict)
                            elif tool_name == "aperag_web_search":
                                ref = _format_web_search_reference(tool_result, args_dict)
                            elif tool_name == "aperag_web_read":
                                ref = _format_web_read_reference(tool_result, args_dict)
                            else:
                                # Generic tool result reference
                                ref = _format_generic_reference(tool_name, tool_result, args_dict)

                            if isinstance(ref, list):
                                references.extend(ref)
                            elif ref:
                                references.append(ref)

                        except (JSONParsingError, ToolReferenceExtractionError) as e:
                            logger.warning(f"Failed to format reference for tool {tool_name}: {e}")
                            continue

                except Exception as e:
                    logger.warning(f"Error processing individual tool call: {e}")
                    continue

    return references


@handle_agent_error("tool_call_reference_extraction", default_return=[], reraise=False)
def extract_tool_call_references(memory) -> List[Dict[str, Any]]:
    """
    Extract tool call results from MCP agent history and format as references.

    Args:
        memory: SimpleMemory instance containing agent history

    Returns:
        List of reference dictionaries in the format expected by llm.py
    """
    history_messages = memory.get() if hasattr(memory, "get") else []
    return _extract_tool_call_references_from_messages(history_messages)


@handle_agent_error("tool_call_reference_extraction", default_return=[], reraise=False)
def extract_tool_call_references_from_messages(history_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract tool call references from a specific history message slice."""
    return _extract_tool_call_references_from_messages(history_messages)


def _extract_answer_faq_ids(messages) -> List[str]:
    """Extract FAQ IDs mentioned in the final assistant answer."""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "assistant" or message.get("tool_calls"):
            continue
        content = message.get("content") or ""
        faq_ids = re.findall(r"FAQ[A-Z]+\d+", content)
        if faq_ids:
            return list(dict.fromkeys(faq_ids))
    return []


def _find_tool_result(messages, tool_call_id: str) -> Optional[str]:
    """Find the tool result message for a given tool call ID"""
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "tool" and message.get("tool_call_id") == tool_call_id:
            content = message.get("content", "")
            logger.debug(f"Found tool result for {tool_call_id}: {type(content)} - {content}")

            # Handle both string and list content
            if isinstance(content, list):
                return json.dumps(content)
            return content
    return None


def _format_search_reference(
    tool_result: str, args: Dict[str, Any], target_faq_ids: Optional[List[str]] = None
) -> Optional[List[Dict[str, Any]]]:
    """Format search_collection tool result as reference"""
    try:
        # Parse tool result - handle both string and already parsed data
        if isinstance(tool_result, str):
            try:
                result_data = json.loads(tool_result)
            except json.JSONDecodeError:
                result_data = {"raw_result": tool_result}
        else:
            result_data = tool_result

        logger.debug(f"Search reference result_data: {result_data}")

        # Handle array format where data is in first element's text field
        if isinstance(result_data, list) and len(result_data) > 0:
            first_item = result_data[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    result_data = text_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse text field as JSON: {first_item['text']}")
                    return None

        # Extract search parameters
        collection_id = args.get("collection_id", "unknown")
        query = args.get("query", "")

        # Format search results
        if "items" in result_data:
            items = result_data["items"]
            if items:
                item, index = _select_primary_reference_item(items, target_faq_ids)
                content = item.get("content", "")
                metadata = item.get("metadata", {}) or {}
                reference_metadata = {
                    **metadata,
                    "type": "search_collection",
                    "collection_id": metadata.get("collection_id") or collection_id,
                    "document_id": metadata.get("document_id") or metadata.get("doc_id"),
                    "query": query,
                    "result_count": len(items),
                    "rank": item.get("rank") or index + 1,
                    "recall_type": item.get("recall_type"),
                    "document_source": item.get("source") or metadata.get("source"),
                }

                return [
                    {
                        "text": _format_reference_content(content, reference_metadata),
                        "metadata": reference_metadata,
                        "score": item.get("score") or 1.0,
                    }
                ]

        return None

    except Exception as e:
        logger.error(f"Error formatting search reference: {e}")
        return None


def _format_search_chat_files_reference(
    tool_result: str, args: Dict[str, Any], target_faq_ids: Optional[List[str]] = None
) -> Optional[List[Dict[str, Any]]]:
    """Format search_chat_files tool result as reference"""
    try:
        # Parse tool result - handle both string and already parsed data
        if isinstance(tool_result, str):
            try:
                result_data = json.loads(tool_result)
            except json.JSONDecodeError:
                result_data = {"raw_result": tool_result}
        else:
            result_data = tool_result

        logger.debug(f"Search chat files reference result_data: {result_data}")

        # Handle array format where data is in first element's text field
        if isinstance(result_data, list) and len(result_data) > 0:
            first_item = result_data[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    result_data = text_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse text field as JSON: {first_item['text']}")
                    return None

        # Extract search parameters
        chat_id = args.get("chat_id", "unknown")
        query = args.get("query", "")

        # Format search results
        if "items" in result_data:
            items = result_data["items"]
            if items:
                item, index = _select_primary_reference_item(items, target_faq_ids)
                content = item.get("content", "")
                metadata = item.get("metadata", {}) or {}
                reference_metadata = {
                    **metadata,
                    "type": "search_chat_files",
                    "chat_id": chat_id,
                    "document_id": metadata.get("document_id") or metadata.get("doc_id"),
                    "query": query,
                    "result_count": len(items),
                    "rank": item.get("rank") or index + 1,
                    "recall_type": item.get("recall_type"),
                    "document_source": item.get("source") or metadata.get("source"),
                }

                return [
                    {
                        "text": _format_reference_content(content, reference_metadata),
                        "metadata": reference_metadata,
                        "score": item.get("score") or 1.0,
                    }
                ]

        return None

    except Exception as e:
        logger.error(f"Error formatting search chat files reference: {e}")
        return None


def _format_reference_content(content: str, metadata: Dict[str, Any]) -> str:
    """Return original chunk markdown with resolvable asset URLs."""
    if not content:
        return ""

    collection_id = metadata.get("collection_id")
    document_id = metadata.get("document_id")
    if not (collection_id and document_id):
        return content

    def add_required_asset_params(match):
        asset_id = match.group(1)
        query = match.group(2) or ""
        query_params = query.lstrip("?")
        additions = []
        if "collection_id=" not in query_params:
            additions.append(f"collection_id={collection_id}")
        if "document_id=" not in query_params:
            additions.append(f"document_id={document_id}")
        if not additions:
            return match.group(0)

        separator = "&" if query_params else ""
        return f"asset://{asset_id}?{query_params}{separator}{'&'.join(additions)}"

    import re

    return re.sub(r"asset://([^\s)\?]+)(\?[^\s)]*)?", add_required_asset_params, content)


def _select_primary_reference_item(
    items: List[Dict[str, Any]], target_faq_ids: Optional[List[str]] = None
) -> tuple[Dict[str, Any], int]:
    """Pick the single chunk users should see when opening references."""
    if target_faq_ids:
        target_ids = set(target_faq_ids)
        for index, item in enumerate(items):
            metadata = item.get("metadata", {}) or {}
            if metadata.get("faq_id") in target_ids:
                return item, index

    for index, item in enumerate(items):
        metadata = item.get("metadata", {}) or {}
        if metadata.get("chunk_type") == "faq_entry":
            return item, index

    return items[0], 0


def _format_list_reference(tool_result: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Format list_collections tool result as reference"""
    try:
        # Parse tool result - handle both string and already parsed data
        if isinstance(tool_result, str):
            try:
                result_data = json.loads(tool_result)
            except json.JSONDecodeError:
                result_data = {"raw_result": tool_result}
        else:
            result_data = tool_result

        logger.debug(f"List reference result_data: {result_data}")

        # Handle array format where data is in first element's text field
        if isinstance(result_data, list) and len(result_data) > 0:
            first_item = result_data[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    result_data = text_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse text field as JSON: {first_item['text']}")
                    return None

        # Look for items field (which contains collections)
        if "items" in result_data:
            collections = result_data["items"]
            text = "Available Collections:\n"
            for collection in collections:
                title = collection.get("title", collection.get("name", "Unknown"))
                description = collection.get("description", "No description")
                collection_id = collection.get("id", "Unknown ID")
                status = collection.get("status", "Unknown")

                text += f"- {title} (ID: {collection_id})\n"
                text += f"  Status: {status}\n"
                if description:
                    text += f"  Description: {description}\n"
                text += "\n"

            return {
                "text": text.strip(),
                "metadata": {"type": "list_collections", "collection_count": len(collections)},
                "score": 1.0,
            }

        return None

    except Exception as e:
        logger.error(f"Error formatting list reference: {e}")
        return None


def _format_web_search_reference(tool_result: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Format web_search tool result as reference"""
    try:
        # Parse tool result - handle both string and already parsed data
        if isinstance(tool_result, str):
            try:
                result_data = json.loads(tool_result)
            except json.JSONDecodeError:
                result_data = {"raw_result": tool_result}
        else:
            result_data = tool_result

        logger.debug(f"Web search reference result_data: {result_data}")

        # Handle array format where data is in first element's text field
        if isinstance(result_data, list) and len(result_data) > 0:
            first_item = result_data[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    result_data = text_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse text field as JSON: {first_item['text']}")
                    return None

        query = args.get("query", "")

        if "results" in result_data:
            results = result_data["results"]
            if results:
                combined_text = f"Web Search Results for: {query}\n\n"

                for result in results:
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    snippet = result.get("snippet", "")

                    combined_text += f"Title: {title}\n"
                    combined_text += f"URL: {url}\n"
                    combined_text += f"Snippet: {snippet}\n\n"

                return {
                    "text": combined_text.strip(),
                    "metadata": {"type": "web_search", "query": query, "result_count": len(results)},
                    "score": 1.0,
                }

        return None

    except Exception as e:
        logger.error(f"Error formatting web search reference: {e}")
        return None


def _format_web_read_reference(tool_result: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Format web_read tool result as reference"""
    try:
        # Parse tool result - handle both string and already parsed data
        if isinstance(tool_result, str):
            try:
                result_data = json.loads(tool_result)
            except json.JSONDecodeError:
                result_data = {"raw_result": tool_result}
        else:
            result_data = tool_result

        logger.debug(f"Web read reference result_data: {result_data}")

        # Handle array format where data is in first element's text field
        if isinstance(result_data, list) and len(result_data) > 0:
            first_item = result_data[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    result_data = text_data
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse text field as JSON: {first_item['text']}")
                    return None

        urls = args.get("url_list", [])

        if "results" in result_data:
            results = result_data["results"]
            if results:
                combined_text = "Web Page Content:\n\n"

                for result in results:
                    url = result.get("url", "No URL")
                    title = result.get("title", "No title")
                    content = result.get("content", "")

                    combined_text += f"URL: {url}\n"
                    combined_text += f"Title: {title}\n"
                    combined_text += f"Content: {content}\n\n"

                return {
                    "text": combined_text.strip(),
                    "metadata": {"type": "web_read", "urls": urls, "result_count": len(results)},
                    "score": 1.0,
                }

        return None

    except Exception as e:
        logger.error(f"Error formatting web read reference: {e}")
        return None


def _format_generic_reference(tool_name: str, tool_result: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Format generic tool result as reference"""
    try:
        # Parse the tool result to handle array format
        parsed_result = tool_result
        if isinstance(tool_result, str):
            try:
                parsed_result = json.loads(tool_result)
            except json.JSONDecodeError:
                parsed_result = tool_result

        # Handle array format where data is in first element's text field
        if isinstance(parsed_result, list) and len(parsed_result) > 0:
            first_item = parsed_result[0]
            if isinstance(first_item, dict) and "text" in first_item:
                try:
                    # Parse the text field as JSON
                    text_data = json.loads(first_item["text"])
                    parsed_result = text_data
                except json.JSONDecodeError:
                    # If parsing fails, use the original text
                    parsed_result = first_item["text"]

        # For generic tools, create a simple reference
        text = f"Tool: {tool_name}\n"
        if args:
            text += f"Arguments: {json.dumps(args, indent=2)}\n"

        # Handle both string and non-string results
        if isinstance(parsed_result, str):
            text += f"Result: {parsed_result}"
        else:
            text += f"Result: {json.dumps(parsed_result, indent=2)}"

        return {
            "text": text,
            "metadata": {"type": "tool_result", "tool_name": tool_name, "args": args},
            "score": 1.0,
        }

    except Exception as e:
        logger.error(f"Error formatting generic reference: {e}")
        return None
