import io
import json
import logging
import os
import re
from typing import Any

from llm_studio.src.utils.plot_utils import PlotData


class IgnorePatchRequestsFilter(logging.Filter):
    """Filter to ignore log entries containing "HTTP Request: PATCH".

    This filter is used to prevent cluttering the logs with PATCH requests,
    which are often generated by the h2o-wave application and not relevant for
    most logging purposes.
    """

    def filter(self, record):
        log_message = record.getMessage()
        if re.search(r"HTTP Request: PATCH", log_message):
            return False  # Ignore the log entry
        return True  # Include the log entry


def initialize_logging(cfg: Any | None = None):
    """
    Initialize logging for the application and for each experiment.

    Console logging is enabled when running in the app context and when running an
    experiment on rank 0 (unless `cfg.logging.log_all_ranks` is set to True, in which
    case all ranks will log to the console).

    Experiment file logging is enabled for rank 0 or all ranks if
    `cfg.logging.log_all_ranks` is set to True.

    For the app logging the log file is created in the llm_studio_workdir with the name
    'h2o_llmstudio.log'.

    """
    if cfg is not None and cfg.logging.log_all_ranks:
        format = "%(asctime)s - PID %(process)d - %(levelname)s: %(message)s"
    else:
        format = "%(asctime)s - %(levelname)s: %(message)s"
    formatter = logging.Formatter(format)

    # Suppress diskcache logs (charts_cache)
    logging.getLogger("diskcache").setLevel(logging.ERROR)

    actual_logger = logging.root
    actual_logger.setLevel(logging.INFO)

    # Only log to console when in the app context or experiment output from rank 0
    # Or user choses to log from all ranks explicitly
    if (cfg is None) or (cfg.environment._local_rank == 0) or cfg.logging.log_all_ranks:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.addFilter(IgnorePatchRequestsFilter())
        actual_logger.addHandler(console_handler)

    file_handler: logging.FileHandler | None = None
    if cfg is not None:
        if (cfg.environment._local_rank == 0) or cfg.logging.log_all_ranks:
            logs_dir = f"{cfg.output_directory}/"
            os.makedirs(logs_dir, exist_ok=True)
            file_handler = logging.FileHandler(filename=f"{logs_dir}/logs.log")
    else:
        try:
            file_handler = logging.FileHandler(filename="h2o_llmstudio.log")
        except PermissionError:
            file_handler = None

    if file_handler is not None:
        file_handler.addFilter(IgnorePatchRequestsFilter())
        file_formatter = logging.Formatter(format)
        file_handler.setFormatter(file_formatter)
        actual_logger.addHandler(file_handler)


class TqdmToLogger(io.StringIO):
    """
    Outputs stream for TQDM.
    It will output to logger module instead of the StdOut.
    """

    logger: logging.Logger = None
    level: int = None
    buf = ""

    def __init__(self, logger, level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO

    def write(self, buf):
        self.buf = buf.strip("\r\n\t [A")

    def flush(self):
        if self.buf != "":
            try:
                self.logger.log(self.level, self.buf)
            except NameError:
                pass


def write_flag(path: str, key: str, value: str):
    """Writes a new flag

    Args:
        path: path to flag json
        key: key of the flag
        value: values of the flag
    """

    if os.path.exists(path):
        with open(path, "r+") as file:
            flags = json.load(file)
    else:
        flags = {}

    flags[key] = value

    with open(path, "w+") as file:
        json.dump(flags, file)


def log_plot(cfg: Any, plot: PlotData, type: str) -> None:
    """Logs a given plot

    Args:
        cfg: cfg
        plot: plot to log
        type: type of the plot

    """
    cfg.logging._logger.log(plot.encoding, type, plot.data)
