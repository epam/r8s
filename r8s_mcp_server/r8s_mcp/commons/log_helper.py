import logging
from pathlib import Path
from sys import stderr

from r8s_mcp.commons.constants import MCPEnv

logger = logging.getLogger(__name__)
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# File handler
log_file = Path.home() / ".r8s-r8s_mcp_server" / "r8s-r8s_mcp_server.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# stderr handler (visible in Claude Desktop logs)
stderr_handler = logging.StreamHandler(stream=stderr)
stderr_handler.setFormatter(formatter)
logger.addHandler(stderr_handler)

logging.captureWarnings(True)


def get_logger(log_name, level=MCPEnv.LOG_LEVEL.get()):
    module_logger = logger.getChild(log_name)
    if level:
        module_logger.setLevel(level)
    return module_logger
