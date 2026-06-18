"""SSE 流式响应助手。各路由复用，避免重复样板。"""
import json
from flask import Response


def sse_response(gen_factory, pre_events=None):
    """
    将一个 yield 字符串的生成器包装为 Flask SSE Response。

    :param gen_factory: 无参可调用，返回 yield str 的生成器（如 lambda: ai_service.chat_stream(...)）
    :param pre_events: 在流式文本前发送的事件列表（如 CSV preview），每项是 dict
    """
    def generate():
        try:
            if pre_events:
                for evt in pre_events:
                    yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
            for chunk in gen_factory():
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'},
    )
