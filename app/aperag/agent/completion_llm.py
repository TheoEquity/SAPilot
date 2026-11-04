"""Expose the SDK's actual completion reason to the chat boundary."""
from copy import copy, deepcopy

from mcp_agent.workflows.llm.augmented_llm import SimpleMemory
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
        instruction = getattr(request_params, 'systemPrompt', None)
        if instruction is None:
            instruction = getattr(self, 'instruction', None)
        if instruction is None:
            return await super().generate(message, request_params)

        # Keep connection resources cached, but bind prompt and memory to this call.
        # The SDK skips system insertion when history is nonempty.
        params = self.get_request_params(request_params)
        params = params.model_copy(update={'systemPrompt': instruction})
        call = copy(self)
        call.instruction = instruction
        call.history = SimpleMemory()
        if params.use_history:
            messages = deepcopy(self.history.get())
            messages = [item for item in messages if item.get('role') != 'system']
            if instruction:
                messages.insert(0, {'role': 'system', 'content': instruction})
            call.history.set(messages)
        try:
            result = await super(CompletionAwareOpenAILLM, call).generate(message, params)
        finally:
            self.last_finish_reason = call.last_finish_reason
            if params.use_history:
                self.history = call.history
        return result

    async def generate_str(self, message, request_params=None):
        responses = await self.generate(message, request_params)
        # The SDK joins every tool-planning preface with the final response.
        # Only the last assistant response is the actual deliverable.
        return (responses[-1].content or '') if responses else ''

    def _annotate_span_for_completion_response(self, span, response, iteration):
        self.last_finish_reason = response.choices[0].finish_reason if response.choices else None
        return super()._annotate_span_for_completion_response(span, response, iteration)
