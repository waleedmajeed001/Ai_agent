import chainlit as cl
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# OpenRouter Gemini 2.0 Flash streaming URL
GEMINI_STREAM_URL = "https://openrouter.ai/api/v1/chat/completions"

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("history", [])

@cl.on_message
async def on_message(message: cl.Message):
    user_input = message.content
    history = cl.user_session.get("history", [])

    # Add user message to history
    history.append({
        "role": "user",
        "content": user_input
    })

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": history,
        "stream": True,
    }

    msg = cl.Message(content="")  # Placeholder for streaming message
    await msg.send()

    full_response = ""

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", GEMINI_STREAM_URL, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip().startswith("data: "):
                        json_data = line[len("data: "):].strip()
                        if json_data == "[DONE]":
                            break
                        try:
                            chunk = httpx.Response(200, content=json_data).json()
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                token = delta.get("content", "")
                                if token:
                                    full_response += token
                                    await msg.stream_token(token)
                        except Exception as e:
                            print(f"🔴 Error parsing stream chunk: {e}")

        # Add assistant's response to history
        history.append({
            "role": "assistant",
            "content": full_response
        })
        cl.user_session.set("history", history)

        # ✅ Finalize the streamed message (removes typing dots)
        await msg.update()

    except Exception as e:
        error_text = f"❌ Streaming error: {str(e)}"
        await cl.Message(content=error_text).send()
