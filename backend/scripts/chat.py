"""Chat with the agent in the terminal, without ElevenLabs. Needs GROQ_API_KEY.

Usage (from backend/): uv run python -m scripts.chat [--caller +919876543210]
"""

import argparse
import asyncio
import uuid

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.graph import get_graph
from app.agent.runner import EndCall, TurnRequest, run_turn, wait_for_background
from app.db.models import CallChannel

GREETING = "Hi, this is Maya from Lauki Phones customer care. How can I help you today?"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caller", help="Simulate a phone call from this number (caller ID)")
    args = parser.parse_args()

    conversation_id = f"cli-{uuid.uuid4()}"
    history: list[BaseMessage] = [AIMessage(GREETING)]
    print(f"Maya: {GREETING}")
    graph = get_graph()

    while True:
        try:
            user = (await asyncio.to_thread(input, "You:  ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user:
            continue
        history.append(HumanMessage(user))
        req = TurnRequest(
            conversation_id=conversation_id,
            channel=CallChannel.phone if args.caller else CallChannel.web,
            caller_number=args.caller,
            history=history,
        )
        print("Maya: ", end="", flush=True)
        reply, ended = "", False
        async for delta in run_turn(req, graph):
            if isinstance(delta, EndCall):
                ended = True
                continue
            reply += delta
            print(delta, end="", flush=True)
        print()
        history.append(AIMessage(reply))
        if ended:
            print("[call ended]")
            break

    await wait_for_background()


if __name__ == "__main__":
    asyncio.run(main())
