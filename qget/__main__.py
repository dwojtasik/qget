"""
qget_cmd
~~~~~~~~~~~~~
Executable version for qget_aio.qget_coro(...)
:copyright: (c) 2022 by Dominik Wojtasik.
:license: Apache2, see LICENSE for more details.
"""

import argparse
import inspect
import logging
import sys
from typing import Any, Dict

from tqdm import tqdm

from qget.qget_aio import ProgressState, qget, qget_coro


def _get_logger() -> logging.Logger:
    """Returns logger for qget script.

    Returns:
        logging.Logger: The configured logger.
    """
    logger = logging.getLogger("qget")
    logger.setLevel(logging.ERROR)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.ERROR)
    logger.addHandler(handler)
    return logger


def _get_qget_default_agrs() -> Dict[str, Any]:
    """Gets default arguments for qget_coro(...) method.

    Returns:
        Dict[str, Any]: The default arguments in format key: value.
    """
    signature = inspect.signature(qget_coro)
    return {k: v.default for k, v in signature.parameters.items() if v.default is not inspect.Parameter.empty}


def _get_parser() -> argparse.ArgumentParser:
    """Returns argument parser for qget command.

    Returns:
        argparse.ArgumentParser: The argument parser.
    """
    default_args = _get_qget_default_agrs()
    parser = argparse.ArgumentParser(
        prog="qget",
        description="Downloads resource from given URL in buffered parts using "
        + "asynchronous HTTP connections with aiohttp session.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        dest="filepath",
        default=default_args["filepath"],
        help="Output path for downloaded resource.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        dest="override",
        default=default_args["override"],
        help="Forces file override for output.",
    )
    parser.add_argument(
        "-a",
        "--auth",
        type=str,
        dest="auth",
        default=default_args["auth"],
        help="String of user:password pair for SSL connection.",
    )
    parser.add_argument(
        "--no-ssl",
        action="store_false",
        dest="verify_ssl",
        default=default_args["verify_ssl"],
        help="Disables SSL certificate validation.",
    )
    parser.add_argument(
        "--no-mock",
        action="store_false",
        dest="mock_browser",
        default=default_args["mock_browser"],
        help="Disables default User-Agent header.",
    )
    parser.add_argument(
        "-H",
        "--header",
        action="append",
        type=str,
        dest="header_list",
        help="Custom header in format 'name:value'.",
    )
    parser.add_argument(
        "-c",
        "--connections",
        type=int,
        dest="max_connections",
        default=default_args["max_connections"],
        help="Maximum amount of asynchronous HTTP connections.",
    )
    parser.add_argument(
        "--test",
        type=int,
        dest="connection_test_sec",
        default=default_args["connection_test_sec"],
        help="Maximum time in seconds assigned to test how much asynchronous connections "
        + "can be achieved to URL. Use 0 to skip.",
    )
    parser.add_argument(
        "--bytes",
        type=int,
        dest="chunk_bytes",
        default=default_args["chunk_bytes"],
        help="Chunk of data read in iteration from url and save to part file in bytes. "
        + "Will be used also when rewriting parts to output file.",
    )
    parser.add_argument(
        "--part",
        type=float,
        dest="max_part_mb",
        default=default_args["max_part_mb"],
        help="Desirable (if possible) max part size in megabytes.",
    )
    parser.add_argument(
        "--tmp",
        type=str,
        dest="tmp_dir",
        default=default_args["tmp_dir"],
        help="Temporary directory path. If not set it points to OS tmp directory.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        default=default_args["debug"],
        help="Debug flag.",
    )
    parser.add_argument("url", type=str, help="URL of resource")
    return parser


def _main():
    """Scipt entrypoint"""
    logger = _get_logger()
    parser = _get_parser()
    progress_bar: tqdm = None
    try:
        args = parser.parse_args()
        kwargs = vars(args)
        url = kwargs.pop("url")

        header_list = kwargs.pop("header_list")
        headers = {}
        if header_list:
            for header_string in header_list:
                if ":" in header_string:
                    name, value = header_string.split(":", 1)
                    headers[name] = value
                else:
                    raise ValueError(
                        f"Custom header has to have format of 'name:value'. Actual value: {header_string}."
                    )
        if len(headers) > 0:
            kwargs["headers"] = headers

        progress_bar = tqdm(
            desc="Download", total=None, miniters=1024, unit="B", unit_scale=True, unit_divisor=1024, delay=sys.maxsize
        )

        def update_download_bar(progress: ProgressState) -> None:
            """Updates tqdm progress bar via callback."""
            if progress.is_download_started():
                if progress_bar.total is None:
                    progress_bar.reset(total=progress.total_bytes)
                    progress_bar.delay = 0
                download_bytes = progress.get_download_bytes()
                progress_bar.update(download_bytes - progress_bar.n)
                if download_bytes == progress.total_bytes:
                    progress_bar.refresh()
                    progress_bar.total = None
                    progress_bar.set_description("Rewrite", refresh=False)
                    progress_bar.fp.write("\n")

        def update_rewrite_bar(progress: ProgressState) -> None:
            """Updates tqdm progress bar via callback. Reuses download progress bar."""
            if progress.is_rewrite_started():
                if progress_bar.total is None:
                    progress_bar.reset(total=progress.total_bytes)
                rewrite_bytes = progress.rewrite_bytes
                progress_bar.update(rewrite_bytes - progress_bar.n)
                if rewrite_bytes == progress.total_bytes:
                    progress_bar.close()

        progress = ProgressState(update_download_bar, update_rewrite_bar)
        kwargs["progress_ref"] = progress
        qget(url, **kwargs)

    except ValueError as ex:
        logger.error(ex)
        sys.exit(1)
    finally:
        if progress_bar is not None and not progress_bar.disable:
            progress_bar.close()


if __name__ == "__main__":
    _main()
