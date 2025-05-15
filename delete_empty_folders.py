import datetime
import os
import pathlib
import socket
import sys
import time
import typing

from send2trash import send2trash

import logging
logger = logging.getLogger()

ignore_these_exact_paths = [
    # NA
]
any_part_of_path_to_ignore = [
    '.git',
    'RECYCLE',
    'System',
]


def any_part_of_path_is_ignored(path) -> bool:
    for part_of_path_to_ignore in any_part_of_path_to_ignore:
        if part_of_path_to_ignore.lower() in path.lower():
            logger.debug(f'Path contains an ignored part: "{part_of_path_to_ignore}".')
            return True
    logger.debug(f'Path contains no ignored parts.')
    return False


def path_is_ignored(path) -> bool:
    if path.lower() in [ignore.lower() for ignore in ignore_these_exact_paths]:
        logger.debug(f'Path is explicitly ignored.')
        return True
    else:
        logger.debug(f'Path is not explicitly ignored.')
        return False


def path_should_be_ignored(path) -> bool:
    if not path_is_ignored(path):
        if not any_part_of_path_is_ignored(path):
            return False
    return True


def dir_is_empty(directory) -> bool:
    for _, _, files in os.walk(directory):
        if files:
            logger.debug(f'Dir is not empty')
            return False
    logger.debug(f'Dir is empty')
    return True


def delete_empty_dirs():
    logger.info("Deleting empty dirs...")

    deleted_dirs = 0
    for root, dirs, _ in os.walk(os.path.dirname(os.path.realpath(__file__)), topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            logger.debug(f'Scanning "{dir_path}"')
            if dir_is_empty(dir_path):
                if path_should_be_ignored(dir_path):
                    continue
                send2trash(dir_path)
                deleted_dirs += 1
                logger.info(f'Deleted "{dir_path}"')

    logger.debug(f"Deleted {deleted_dirs} dir(s).")


def main():
    start_time = time.perf_counter()

    delete_empty_dirs()

    end_time = time.perf_counter()
    duration = end_time - start_time
    logger.info(f'Completed operation in {duration:.4f}s.')


def setup_logging(
        logger: logging.Logger,
        log_file_path: typing.Union[str, os.PathLike[str]],
        number_of_logs_to_keep: typing.Union[int, None] = None,
        console_logging_level: int = logging.DEBUG,
        file_logging_level: int = logging.DEBUG,
        log_message_format: str = '%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] [%(name)s]: %(message)s',
        date_format: str = '%Y-%m-%d %H:%M:%S') -> None:
    # Initialize logs folder
    log_dir = os.path.dirname(log_file_path)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)  # Create logs dir if it does not exist

    # Limit # of logs in logs folder
    if number_of_logs_to_keep is not None:
        log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')], key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
        if len(log_files) >= number_of_logs_to_keep:
            for file in log_files[:len(log_files) - number_of_logs_to_keep + 1]:
                os.remove(os.path.join(log_dir, file))

    logger.setLevel(file_logging_level)  # Set the overall logging level

    # File Handler for date-based log file
    file_handler_date = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler_date.setLevel(file_logging_level)
    file_handler_date.setFormatter(logging.Formatter(log_message_format))
    logger.addHandler(file_handler_date)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_logging_level)
    console_handler.setFormatter(logging.Formatter(log_message_format, datefmt=date_format))
    logger.addHandler(console_handler)

    # Set specific logging levels
    # logging.getLogger('requests').setLevel(logging.INFO)
    # logging.getLogger('sys').setLevel(logging.CRITICAL)
    # logging.getLogger('urllib3').setLevel(logging.INFO)


if __name__ == "__main__":
    pc_name = socket.gethostname()
    script_name = pathlib.Path(os.path.basename(__file__)).stem
    log_dir = pathlib.Path(f"{script_name} Logs")
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    log_file_name = pathlib.Path(f'{timestamp}_{pc_name}.log')
    log_file_path = os.path.join(log_dir, log_file_name)
    setup_logging(logger, log_file_path, number_of_logs_to_keep=10)

    error = 0
    try:
        main()
    except Exception as e:
        logger.warning(f'A fatal error has occurred due to {repr(e)}')
        error = 1
    finally:
        exit(error)
