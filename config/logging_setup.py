import json
import logging
import sys
from datetime import UTC, datetime

from config.constants import LogFields
from config.settings import LoggingSettings

# attributes every LogRecord has; anything else was passed through `extra=`
_STANDARD_RECORD_FIELDS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Format each log record as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            LogFields.TIMESTAMP: datetime.fromtimestamp(
                record.created, UTC
            ).isoformat(),
            LogFields.LEVEL: record.levelname,
            LogFields.LOGGER: record.name,
            LogFields.MESSAGE: record.getMessage(),
        }
        # context passed as logger.info("...", extra={"tool": "read"})
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_FIELDS:
                entry[key] = value
        if record.exc_info:
            entry[LogFields.EXCEPTION] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(settings: LoggingSettings) -> None:
    """Send all logs to stderr (or a file) as JSON lines. Call once at startup."""
    handler: logging.Handler
    if settings.log_file is None:
        handler = logging.StreamHandler(sys.stderr)
    else:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(settings.log_file)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.level)
    for name in settings.quiet_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
