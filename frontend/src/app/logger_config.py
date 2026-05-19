import logging
from pythonjsonlogger.json import JsonFormatter

logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger.addHandler(handler)

logger.info("Logging using python-json-logger!", extra={"more_data": True})
