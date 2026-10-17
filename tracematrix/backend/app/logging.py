import logging
import sys
import uuid
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    logging.basicConfig(
        level=level.upper(),
        format='{"ts":"%(asctime)s","level":"%(levelname)s","request_id":"%(request_id)s","logger":"%(name)s","msg":"%(message)s"}',
        handlers=[handler],
        force=True,
    )


def new_request_id() -> str:
    value = str(uuid.uuid4())
    request_id_ctx.set(value)
    return value
