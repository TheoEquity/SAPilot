"""Expose the SDK's actual completion reason to the chat boundary."""
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM


class CompletionAwareOpenAILLM(OpenAIAugmentedLLM):
    last_finish_reason: str | None = None

    async def generate(self, message, request_params=None):
        self.last_finish_reason = None
        if request_params is not None:
            metadata = dict(request_params.metadata or {})
            temperature = getattr(request_params, 'temperature', None)
            if temperature is not None and request_params.model and not self._reasoning(request_params.model):
                metadata.setdefault('temperature', temperature)
            if request_params.model == 'qwen3.8-flash':
                extra_body = dict(metadata.get('extra_body') or {})
                extra_body.setdefault('enable_thinking', False)
                metadata['extra_body'] = extra_body
            request_params = request_params.model_copy(update={'metadata': metadata})
        return await super().generate(message, request_params)

    async def generate_str(self, message, request_params=None):
        responses = await self.generate(message, request_params)
        # The SDK joins every tool-planning preface with the final response.
        # Only the last assistant response is the actual deliverable.
        return (responses[-1].content or '') if responses else ''

    def _annotate_span_for_completion_response(self, span, response, iteration):
        self.last_finish_reason = response.choices[0].finish_reason if response.choices else None
        return super()._annotate_span_for_completion_response(span, response, iteration)
