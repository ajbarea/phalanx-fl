"""Terminal WebSocket router for interactive shell sessions."""

from __future__ import annotations

import asyncio
import concurrent.futures
import datetime
import json
import logging
import os
import shutil
import struct
import subprocess
import sys
from contextlib import suppress
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from intellifl.api.dependencies import BASE_DIR, get_safe_env

if sys.platform == "win32":
    import winpty
else:
    import fcntl
    import pty
    import select
    import termios

logger = logging.getLogger(__name__)

router = APIRouter(tags=["terminal"])

# Active terminal session tracking
terminal_sessions: dict[str, dict[str, Any]] = {}


if sys.platform == "win32":

    @router.websocket("/api/terminal")
    async def terminal_websocket(websocket: WebSocket):
        """Manages interactive terminal sessions over WebSocket for Windows."""
        await websocket.accept()

        session_id = f"term_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        logger.info(f"Terminal session started: {session_id}")

        bash_path = shutil.which("bash")
        if bash_path:
            shell_cmd = [bash_path]
            logger.info(f"Using bash: {bash_path}")
        else:
            shell_path = os.environ.get("COMSPEC", "cmd.exe")
            shell_cmd = [shell_path]
            logger.info(f"Bash not found, using cmd.exe: {shell_path}")

        env = get_safe_env()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        proc = winpty.PtyProcess.spawn(
            shell_cmd,
            cwd=str(BASE_DIR),
            dimensions=(24, 80),
            env=env,
        )

        terminal_sessions[session_id] = {"process": proc}

        async def read_from_pty():
            loop = asyncio.get_event_loop()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

            def blocking_read():
                try:
                    return proc.read()
                except EOFError:
                    return None
                except Exception as e:
                    logger.debug(f"PTY read exception: {e}")
                    return None

            try:
                while proc.isalive():
                    try:
                        future = loop.run_in_executor(executor, blocking_read)
                        try:
                            data = await asyncio.wait_for(future, timeout=0.5)
                            if data:
                                logger.debug(f"PTY data: {len(data)} bytes")
                                await websocket.send_text(data)
                            else:
                                await asyncio.sleep(0.05)
                        except TimeoutError:
                            await asyncio.sleep(0.01)
                            continue
                    except EOFError:
                        logger.debug("PTY EOF")
                        break
                    except Exception as e:
                        logger.debug(f"PTY read loop error: {e}")
                        await asyncio.sleep(0.05)
            except Exception:
                logger.exception("PTY read error")
            finally:
                executor.shutdown(wait=False)

        read_task = asyncio.create_task(read_from_pty())

        try:
            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if "text" in message:
                    text = message["text"]

                    if text.startswith("{"):
                        try:
                            msg = json.loads(text)
                            if msg.get("type") == "resize":
                                rows = max(1, min(500, int(msg.get("rows", 24))))
                                cols = max(1, min(500, int(msg.get("cols", 80))))
                                proc.setwinsize(rows, cols)
                                logger.debug(f"Terminal resized to {rows}x{cols}")
                                continue
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                    try:
                        proc.write(text)
                    except Exception:
                        logger.exception("PTY write error")
                        break

        except WebSocketDisconnect:
            logger.info(f"Terminal session disconnected: {session_id}")
        except Exception:
            logger.exception("Terminal WebSocket error")
        finally:
            read_task.cancel()
            with suppress(asyncio.CancelledError):
                await read_task

            if proc.isalive():
                proc.terminate()

            if session_id in terminal_sessions:
                del terminal_sessions[session_id]

            logger.info(f"Terminal session ended: {session_id}")

else:

    def _set_terminal_size(fd: int, rows: int, cols: int) -> None:
        """Sets the terminal size for a PTY file descriptor."""
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    @router.websocket("/api/terminal")
    async def terminal_websocket(websocket: WebSocket):
        """Manages interactive terminal sessions over WebSocket for Unix."""
        await websocket.accept()

        session_id = f"term_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        logger.info(f"Terminal session started: {session_id}")

        master_fd, slave_fd = pty.openpty()
        _set_terminal_size(master_fd, 24, 80)

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        env = get_safe_env()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        process = subprocess.Popen(
            ["/bin/bash"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(BASE_DIR),
            env=env,
            preexec_fn=os.setsid,
        )

        os.close(slave_fd)

        terminal_sessions[session_id] = {
            "process": process,
            "master_fd": master_fd,
        }

        async def read_from_pty():
            try:
                while True:
                    await asyncio.sleep(0.01)

                    if process.poll() is not None:
                        break

                    try:
                        ready, _, _ = select.select([master_fd], [], [], 0)
                        if ready:
                            data = os.read(master_fd, 4096)
                            if data:
                                await websocket.send_text(data.decode("utf-8", errors="replace"))
                    except (OSError, BlockingIOError):
                        pass

            except Exception:
                logger.exception("PTY read error")

        read_task = asyncio.create_task(read_from_pty())

        try:
            while True:
                message = await websocket.receive()

                if message["type"] == "websocket.disconnect":
                    break

                if "text" in message:
                    text = message["text"]

                    if text.startswith("{"):
                        try:
                            msg = json.loads(text)
                            if msg.get("type") == "resize":
                                rows = max(1, min(500, int(msg.get("rows", 24))))
                                cols = max(1, min(500, int(msg.get("cols", 80))))
                                _set_terminal_size(master_fd, rows, cols)
                                logger.debug(f"Terminal resized to {rows}x{cols}")
                                continue
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass

                    try:
                        os.write(master_fd, text.encode("utf-8"))
                    except OSError:
                        logger.exception("PTY write error")
                        break

        except WebSocketDisconnect:
            logger.info(f"Terminal session disconnected: {session_id}")
        except Exception:
            logger.exception("Terminal WebSocket error")
        finally:
            read_task.cancel()
            with suppress(asyncio.CancelledError):
                await read_task

            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

            os.close(master_fd)

            if session_id in terminal_sessions:
                del terminal_sessions[session_id]

            logger.info(f"Terminal session ended: {session_id}")
