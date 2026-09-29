import json
import uuid
from collections.abc import Iterator
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


def tool_call(name: str, **args: Any) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": name, "args": args, "id": f"call_{uuid.uuid4().hex[:8]}"}]
    )


class ScriptedChatModel(BaseChatModel):
    """Replays a fixed list of AI messages (text or tool calls), streaming them like a real LLM."""

    responses: list[AIMessage]
    calls: list[list[BaseMessage]] = []
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        self.calls.append(list(messages))
        response = self.responses[min(self.cursor, len(self.responses) - 1)]
        self.cursor += 1
        return response

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        response = self._next(messages)
        if response.tool_calls:
            chunks = [
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": tc["name"],
                            "args": json.dumps(tc["args"]),
                            "id": tc["id"],
                            "index": i,
                        }
                        for i, tc in enumerate(response.tool_calls)
                    ],
                )
            ]
        else:
            words = str(response.content).split(" ")
            chunks = [
                AIMessageChunk(content=w + (" " if i < len(words) - 1 else ""))
                for i, w in enumerate(words)
            ]
        for chunk in chunks:
            generation = ChatGenerationChunk(message=chunk)
            if run_manager:
                run_manager.on_llm_new_token(str(chunk.content), chunk=generation)
            yield generation
