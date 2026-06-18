"""★ WebSocket live-просмотр партии: replay событий сессии + стрим новых (D-002).

Партия играется в фоновом потоке (``GameManager``), а её события копятся в
``GameSession.events``. WebSocket-эндпоинт сначала **переигрывает** уже накопленные
события (подключившийся позже видит партию с начала), затем **дослеживает** новые,
опрашивая буфер, пока партия не завершится. Так один и тот же поток событий годится
и для наблюдения вживую, и для подключения к уже сыгранной партии.

События обогащаются для фронтенда: к кадрам с позицией (`fen`) добавляется
inline-SVG доски (с подсветкой последнего хода, если он известен), а к ходам —
рассуждение модели из ``GameRecord``. Клиенту остаётся вставить SVG и текст —
рендер на сервере (как в отчёте, D-013), без шахматной логики на фронте.
"""

from __future__ import annotations

import asyncio

from fastapi import WebSocket, WebSocketDisconnect

from arena.report import move_animation, piece_svg, render_board_svg
from arena.web.games import GameSession

# Пауза между опросами буфера событий фоновой партии (с).
_POLL_INTERVAL = 0.05


def enrich_event(event: dict, session: GameSession) -> dict:
    """Дополнить событие данными для отрисовки: SVG доски и рассуждение хода.

    К любому событию с позицией (`fen` в нагрузке) добавляется ``svg`` (inline-доска,
    с подсветкой хода по `uci`, если есть). К событиям хода (`move`) добавляются
    ``reasoning`` соответствующего ``MoveRecord`` и ``anim`` — данные скольжения
    фигуры (центры from/to в долях доски + inline-SVG фигуры) для плавного хода на
    фронте. Исходное событие не мутируется.
    """
    payload = event["payload"]
    data = dict(payload)
    fen = payload.get("fen")
    if fen:
        data["svg"] = render_board_svg(fen, lastmove_uci=payload.get("uci"))
    ply = payload.get("ply")
    if event["type"] == "move" and isinstance(ply, int):
        index = ply - 1
        if 0 <= index < len(session.record.moves):
            record = session.record.moves[index]
            data["reasoning"] = record.reasoning
            anim = move_animation(record.fen_before, record.uci)
            if anim is not None:
                for sub in anim["moves"]:
                    sub["piece"] = piece_svg(sub["pc"]) if sub["pc"] else ""
                data["anim"] = anim
    return {"type": event["type"], "payload": data}


async def stream_session(websocket: WebSocket, session: GameSession | None) -> None:
    """Транслировать события партии в WebSocket: replay + стрим до завершения.

    Неизвестная партия → один кадр ``error`` и закрытие. Иначе: по очереди шлём все
    события (обогащённые), затем ждём новые, пока ``session.done``; в конце —
    итоговый кадр ``status`` (статус/результат/причина/ошибка) и закрытие.
    Отключение клиента (``WebSocketDisconnect``) гасится молча.
    """
    await websocket.accept()
    if session is None:
        await websocket.send_json(
            {"type": "error", "payload": {"message": "unknown game"}}
        )
        await websocket.close()
        return

    sent = 0
    try:
        while True:
            while sent < len(session.events):
                await websocket.send_json(enrich_event(session.events[sent], session))
                sent += 1
            if session.done:
                break
            await asyncio.sleep(_POLL_INTERVAL)
        await websocket.send_json(
            {
                "type": "status",
                "payload": {
                    "status": session.status,
                    "result": session.result,
                    "termination": session.termination,
                    "error": session.error,
                },
            }
        )
        await websocket.close()
    except WebSocketDisconnect:
        return
