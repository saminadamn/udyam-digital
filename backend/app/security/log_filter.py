"""PII-safe logging (DESIGN.md D2.8). Every log record from any logger (ours, uvicorn's access log with request paths such as
/kyc/gstin/{gstin}, libraries) is scrubbed when it is created, so no handler or child logger can print a raw GSTIN, Udyam number,
PAN or phone. A logger-level filter alone misses records that propagate from child loggers."""
import logging

from app.security.masking import scrub

_installed = False


def _clean(record: logging.LogRecord) -> logging.LogRecord:
    if isinstance(record.msg, str):
        record.msg = scrub(record.msg)
    if isinstance(record.args, tuple):
        # Only strings can carry an ID; numbers stay numbers so %d placeholders (uvicorn's access log) still format.
        record.args = tuple(scrub(a) if isinstance(a, str) else a for a in record.args)
    elif isinstance(record.args, dict):
        record.args = {k: scrub(v) if isinstance(v, str) else v for k, v in record.args.items()}
    return record


class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        _clean(record)
        return True


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    base = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        return _clean(base(*args, **kwargs))

    logging.setLogRecordFactory(factory)
    f = PIIFilter()
    for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "app"):
        logging.getLogger(name).addFilter(f)
