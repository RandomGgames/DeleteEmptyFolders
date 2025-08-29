import logging
import os
import pathlib
import socket
import sys
import time
import toml
import traceback
import typing

from datetime import datetime
from send2trash import send2trash

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.toml") -> dict:
    logger.debug("Loading config...")
    required_keys = {"cache", "media_dir"}
    config = toml.load(config_path)

    logger.debug("Validating config...")
    required_keys = {
        "path_to_scan": str,
        "ignore_these_exact_paths": list,
        "any_part_of_path_to_ignore": list
    }
    for key, expected_type in required_keys.items():
        if key not in config or not isinstance(config[key], expected_type):
            raise ValueError(
                f"config.toml is missing or has incorrect type for key '{key}' (expected {expected_type.__name__})")
    if not all(key in config for key in required_keys):
        raise ValueError(
            f"config.toml is missing required key(s): {', '.join(sorted(list(set(required_keys) - set(config.keys()))))}")
    logger.debug("Config loaded successfully.")
    return config


def path_is_ignored(path: str, ignore_these_exact_paths: typing.List[str], any_part_of_path_to_ignore: typing.List[str]) -> bool:
    if path.lower() in [ignore.lower() for ignore in ignore_these_exact_paths]:
        logger.debug(f"Path is explicitly ignored.")
        return True
    if any(part_of_path_to_ignore.lower() in path.lower() for part_of_path_to_ignore in any_part_of_path_to_ignore):
        logger.debug(f"Path contains an ignored part.")
        return True
    logger.debug(f"Path is not explicitly ignored and contains no ignored parts.")
    return False


def dir_is_empty(directory) -> bool:
    for _, _, files in os.walk(directory):
        if files:
            logger.debug(f"Dir is not empty")
            return False
    logger.debug(f"Dir is empty")
    return True


def main():
    config = load_config()
    path_to_scan = str(config["path_to_scan"])
    ignore_these_exact_paths = list(config["ignore_these_exact_paths"])
    any_part_of_path_to_ignore = list(config["any_part_of_path_to_ignore"])

    logger.info("Deleting empty dirs...")

    deleted_dirs = 0
    for root, dirs, _ in os.walk(os.path.dirname(os.path.realpath(path_to_scan)), topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            logger.debug(f"Scanning '{dir_path}'")
            if dir_is_empty(dir_path):
                if path_is_ignored(dir_path, ignore_these_exact_paths, any_part_of_path_to_ignore):
                    continue
                try:
                    send2trash(dir_path)
                    deleted_dirs += 1
                    logger.info(f"Deleted '{dir_path}'")
                except Exception as e:
                    logger.error(f"Failed to delete '{dir_path}': {e}")
                    logger.error(traceback.format_exc())

    logger.debug(f"Deleted {deleted_dirs} dir(s).")


def setup_logging(
        logger: logging.Logger,
        log_file_path: typing.Union[str, pathlib.Path],
        number_of_logs_to_keep: typing.Union[int, None] = None,
        console_logging_level: int = logging.DEBUG,
        file_logging_level: int = logging.DEBUG,
        log_message_format: str = "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] [%(name)s]: %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S") -> None:
    # Ensure log_dir is a Path object
    log_file_path = pathlib.Path(log_file_path)
    log_dir = log_file_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)  # Create logs dir if it does not exist

    # Limit # of logs in logs folder
    if number_of_logs_to_keep is not None:
        log_files = sorted([f for f in log_dir.glob("*.log")], key=lambda f: f.stat().st_mtime)
        if len(log_files) >= number_of_logs_to_keep:
            for file in log_files[:len(log_files) - number_of_logs_to_keep + 1]:
                file.unlink()

    logger.setLevel(file_logging_level)  # Set the overall logging level

    # File Handler for date-based log file
    file_handler_date = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler_date.setLevel(file_logging_level)
    file_handler_date.setFormatter(logging.Formatter(log_message_format, datefmt=date_format))
    logger.addHandler(file_handler_date)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_logging_level)
    console_handler.setFormatter(logging.Formatter(log_message_format, datefmt=date_format))
    logger.addHandler(console_handler)

    # Set specific logging levels if needed
    # logging.getLogger("requests").setLevel(logging.INFO)


if __name__ == "__main__":
    pc_name = socket.gethostname()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    script_name = pathlib.Path(__file__).stem
    log_dir = pathlib.Path(f"{script_name} Logs")
    log_file_name = f"{timestamp}_{pc_name}.log"
    log_file_path = log_dir / log_file_name
    setup_logging(logger, log_file_path, number_of_logs_to_keep=100, log_message_format="%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s")

    error = 0
    try:
        start_time = time.perf_counter()
        logger.info("Starting operation...")
        main()
        end_time = time.perf_counter()
        duration = end_time - start_time
        logger.info(f"Completed operation in {duration:.4f}s.")
    except Exception as e:
        logger.warning(f"A fatal error has occurred: {repr(e)}\n{traceback.format_exc()}")
        error = 1
    finally:
        sys.exit(error)
