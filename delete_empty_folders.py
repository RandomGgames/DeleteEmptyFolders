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

"""
Delete Empty Folders

Deletes empty folders in the specified directory tree.
"""

__version__ = "1.1.1"  # Major.Minor.Patch


def read_toml(file_path: typing.Union[str, pathlib.Path]) -> dict:
    """
    Read configuration settings from the TOML file.
    """
    file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    config = toml.load(file_path)
    return config


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


def dir_is_empty(path) -> bool:
    if not os.path.isdir(path):
        logger.debug(f"Path is not a directory")
        return False
    for _, _, files in os.walk(path):
        if files:
            logger.debug(f"Dir is not empty")
            return False
    logger.debug(f"Dir is empty")
    return True


def main():
    path_to_scan = os.path.realpath(str(config["path_to_scan"]))
    ignore_these_exact_paths = list(config["ignore_these_exact_paths"])
    any_part_of_path_to_ignore = list(config["any_part_of_path_to_ignore"])

    logger.info(f"Deleting empty dirs in '{path_to_scan}'...")

    deleted_dirs = 0
    for root, dirs, _ in os.walk(path_to_scan, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            logger.debug(f"Scanning '{dir_path}'")
            if path_is_ignored(dir_path, ignore_these_exact_paths, any_part_of_path_to_ignore):
                continue
            if not dir_is_empty(dir_path):
                continue
            try:
                send2trash(dir_path)
                deleted_dirs += 1
                logger.info(f"Deleted '{dir_path}'")
            except Exception as e:
                logger.error(f"Failed to delete '{dir_path}': {e}")
                logger.error(traceback.format_exc())

    logger.debug(f"Deleted {deleted_dirs} dir(s).")


def format_duration_long(duration_seconds: float) -> str:
    """
    Format duration in a human-friendly way, showing only the two largest non-zero units.
    For durations >= 1s, do not show microseconds or nanoseconds.
    For durations >= 1m, do not show milliseconds.
    """
    ns = int(duration_seconds * 1_000_000_000)
    units = [
        ('y', 365 * 24 * 60 * 60 * 1_000_000_000),
        ('mo', 30 * 24 * 60 * 60 * 1_000_000_000),
        ('d', 24 * 60 * 60 * 1_000_000_000),
        ('h', 60 * 60 * 1_000_000_000),
        ('m', 60 * 1_000_000_000),
        ('s', 1_000_000_000),
        ('ms', 1_000_000),
        ('us', 1_000),
        ('ns', 1),
    ]
    parts = []
    for name, factor in units:
        value, ns = divmod(ns, factor)
        if value:
            parts.append(f"{value}{name}")
        # Stop after two largest non-zero units
        if len(parts) == 2:
            break
    if not parts:
        return "0s"
    return "".join(parts)


def setup_logging(
        logger: logging.Logger,
        log_file_path: typing.Union[str, pathlib.Path],
        number_of_logs_to_keep: typing.Union[int, None] = None,
        console_logging_level: int = logging.DEBUG,
        file_logging_level: int = logging.DEBUG,
        log_message_format: str = "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] [%(name)s]: %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S") -> None:
    log_file_path = pathlib.Path(log_file_path)
    log_dir = log_file_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Limit # of logs in logs folder
    if number_of_logs_to_keep is not None:
        log_files = sorted([f for f in log_dir.glob("*.log")], key=lambda f: f.stat().st_mtime)
        if len(log_files) > number_of_logs_to_keep:
            for file in log_files[:-number_of_logs_to_keep]:
                file.unlink()

    # Clear old handlers to avoid duplication
    logger.handlers.clear()
    logger.setLevel(file_logging_level)

    formatter = logging.Formatter(log_message_format, datefmt=date_format)

    # File Handler
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(file_logging_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_logging_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


if __name__ == "__main__":
    config_path = pathlib.Path("config.toml")
    if not config_path.exists():
        raise FileNotFoundError(f"Missing {config_path}")
    global config
    config = read_toml(config_path)

    console_logging_level = getattr(logging, config.get("logging", {}).get("console_logging_level", "INFO").upper(), logging.DEBUG)
    file_logging_level = getattr(logging, config.get("logging", {}).get("file_logging_level", "INFO").upper(), logging.DEBUG)
    logs_file_path = config.get("logging", {}).get("logs_file_path", "logs")
    use_logs_folder = config.get("logging", {}).get("use_logs_folder", True)
    number_of_logs_to_keep = config.get("logging", {}).get("number_of_logs_to_keep", 10)
    log_message_format = config.get("logging", {}).get(
        "log_message_format",
        "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s"
    )

    script_name = pathlib.Path(__file__).stem
    pc_name = socket.gethostname()
    if use_logs_folder:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_dir = pathlib.Path(f"{logs_file_path}/{script_name}")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_name = f"{timestamp}_{script_name}_{pc_name}.log"
        log_file_path = log_dir / log_file_name
    else:
        log_file_path = pathlib.Path(f"{script_name}_{pc_name}.log")

    setup_logging(
        logger,
        log_file_path,
        console_logging_level=console_logging_level,
        file_logging_level=file_logging_level,
        number_of_logs_to_keep=number_of_logs_to_keep,
        log_message_format=log_message_format
    )

    error = 0
    try:
        start_time = time.perf_counter_ns()
        logger.info(f"Script: {script_name} | Version: {__version__} | Host: {pc_name}")

        main()
        end_time = time.perf_counter_ns()
        duration = end_time - start_time
        duration = format_duration_long(duration / 1e9)
        logger.info(f"Execution completed in {duration}.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted by user.")
        error = 130
    except Exception as e:
        logger.warning(f"A fatal error has occurred: {repr(e)}\n{traceback.format_exc()}")
        error = 1
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()
        sys.exit(error)
