import asyncio
import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from teams import nba_analysis_team

logger = logging.getLogger(__name__)

router = APIRouter()

def format_sse(data: str, event: str | None = None) -> str:
    msg = f"data: {data}\n\n"
    if event is not None:
        msg = f"event: {event}\n{msg}"
    # Add padding to force flush
    msg += ":" + (" " * 2048) + "\n\n"
    return msg

@router.get("/ask_team")
async def ask_team_keepalive_sse(request: Request, prompt: str):
    logger.info(f"Received GET /ask_team request with prompt: '{prompt}'")
    team_instance = nba_analysis_team

    async def keepalive_sse_generator():
        logger.info(f"START keepalive_sse_generator for prompt: '{prompt}'")
        agent_task = None
        keep_alive_interval = 5
        mock_messages = ["Analyzing data...", "Consulting sources...", "Synthesizing findings...", "Cross-referencing stats...", "Checking historical trends...", "Almost there..."]
        msg_index = 0
        try:
            yield format_sse(json.dumps({"type": "status", "message": "Processing prompt..."}))
            await asyncio.sleep(0.1)
            yield format_sse(json.dumps({"type": "status", "message": "Starting agent execution..."}))
            await asyncio.sleep(0.1)

            logger.info(f"Starting Agno agent for prompt: {prompt}")
            agent_task = asyncio.create_task(team_instance.arun(prompt))

            while not agent_task.done():
                if await request.is_disconnected():
                    logger.warning("Client disconnected, cancelling agent task.")
                    agent_task.cancel()
                    raise asyncio.CancelledError("Client disconnected during keep-alive")

                status_msg = mock_messages[msg_index % len(mock_messages)]
                yield format_sse(json.dumps({"type": "status", "message": status_msg}))
                logger.debug(f"Sent keep-alive status: {status_msg}")
                msg_index += 1

                wait_step = 0.5
                for _ in range(int(keep_alive_interval / wait_step)):
                    if agent_task.done() or await request.is_disconnected():
                        break
                    await asyncio.sleep(wait_step)
                if agent_task.done() or await request.is_disconnected():
                    break

            if await request.is_disconnected():
                if agent_task and not agent_task.done():
                    agent_task.cancel()
                raise asyncio.CancelledError("Client disconnected before agent completion")

            result = await agent_task
            logger.info(f"Agno agent completed for prompt: {prompt}")
            final_content = result.content

            if final_content is None:
                logger.error("Agent did not produce a recognizable final response.")
                yield format_sse(json.dumps({"type": "error", "message": "Agent did not produce a recognizable final response."}))
            else:
                logger.debug(f"Sending final content via SSE: {final_content[:100]}...")
                final_sse_data = {"type": "final_response", "content": final_content}
                yield format_sse(json.dumps(final_sse_data), event="final")

        except asyncio.CancelledError:
            logger.warning("SSE task cancelled.")
            if agent_task and not agent_task.done():
                agent_task.cancel()
        except Exception as e:
            logger.exception("Error during SSE generation")
            error_detail = f"Error processing team request: {str(e)}"
            try:
                yield format_sse(json.dumps({"type": "error", "message": error_detail}))
            except Exception as send_err:
                logger.error(f"Failed to send error message: {send_err}")
        finally:
            logger.info("END keepalive_sse_generator.")

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(keepalive_sse_generator(), headers=headers)