"""
qget_aio
~~~~~~~~~~~~~
Coroutine for downloading files fast with asyncio and aiohttp
:copyright: (c) 2022 by Dominik Wojtasik.
:license: Apache2, see LICENSE for more details.
"""

import asyncio
import glob
import logging
import math
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Callable, Dict
from urllib.parse import unquote, urlparse

import aiofiles
import aiohttp

_UNITS = ["B", "KB", "MB", "GB", "TB"]


@dataclass
class PartData:
    """Holds basic information for part downloading.

    part_id (str): Unique part identifier used as part of filename.
    begin (int): An integer indicating the start position or request range in bytes.
    end (int): An integer indicating the end position or request range in bytes.
    """

    part_id: str
    begin: int
    end: int


class ProgressState:
    """Holds progress state for downloaded resource.

    parts_bytes (Dict[str, int]): Dictionary of part identifier to it's current downloaded bytes count.
    total_bytes (int): The downloaded resource byte count.
    rewrite_bytes (int): The rewritten byte count from parts file to output files.
    download_start_timestamp_ms (int): Timestamp of download start in milliseconds since the Epoch.
    download_end_timestamp_ms (int): Timestamp of download end in milliseconds since the Epoch.
        Used also as rewrite start timestamp.
    rewrite_end_timestamp_ms (int): Timestamp of file joining end in milliseconds since the Epoch.
    on_download_progress (Callable[[ProgressState], None]): Callback that is called every download state change.
    on_rewrite_progress (Callable[[ProgressState], None]): Callback that is called every rewrite state change.
    """

    def __init__(
        self,
        on_download_progress: Callable[["ProgressState"], None] = None,
        on_rewrite_progress: Callable[["ProgressState"], None] = None,
    ):
        self.parts_bytes: Dict[str, int] = {}
        self.total_bytes = 0
        self.rewrite_bytes = 0
        self.download_start_timestamp_ms = 0
        self.download_end_timestamp_ms = 0
        self.rewrite_end_timestamp_ms = 0
        self.on_download_progress = on_download_progress
        self.on_rewrite_progress = on_rewrite_progress

    def init_parts_bytes(self, part_count: int, part_zfill: int) -> None:
        """Initializes values in dictionary for parts download progress.

        Args:
            part_count (int): Count of parts to be downloaded.
            part_zfill (int): Number of leading zeros in part identifier.
        """
        self.parts_bytes = {str(part).zfill(part_zfill): 0 for part in range(part_count)}

    def update_part_progress(self, part_id: str, byte_count: int) -> None:
        """Updates value of current downloaded bytes count for given part identifier.

        Calls self.on_download_progress callback if set.

        Args:
            part_id (str): The part identifier.
            byte_count (int): Count of new bytes that were downloaded since last update.
        """
        self.parts_bytes[part_id] += byte_count
        if self.on_download_progress:
            self.on_download_progress(self)

    def update_rewrite_progress(self, byte_count: int) -> None:
        """Updates value of rewrite progress.

        Calls self.on_rewrite_progress callback if set.

        Args:
            byte_count (int): Count of bytes that was rewritten into output file.
        """
        self.rewrite_bytes = byte_count
        if self.on_rewrite_progress:
            self.on_rewrite_progress(self)

    def get_download_bytes(self) -> int:
        """Returns overall download byte count.

        Returns:
            int: The overall download byte count.
        """
        return sum(self.parts_bytes.values())

    def get_download_progress(self) -> float:
        """Returns overall download progress in percent[%].

        Returns:
            float: The overall download progress in percent[%].
        """
        if self.total_bytes == 0:
            return 0
        return self.get_download_bytes() / self.total_bytes * 100

    def get_rewrite_progress(self) -> float:
        """Returns overall progress of rewriting part files to output file in percent[%]

        Returns:
            float: The rewriting progress in percent [%].
        """
        if self.total_bytes == 0:
            return 0
        return self.rewrite_bytes / self.total_bytes * 100

    def is_download_started(self) -> bool:
        """Checks if download has been started.

        Returns:
            bool: True if download has been started.
        """
        return self.download_start_timestamp_ms > 0

    def is_rewrite_started(self) -> bool:
        """Checks if rewrite has been started.

        Returns:
            bool: True if rewrite has been started.
        """
        return self.download_end_timestamp_ms > 0


def _get_logger(debug: bool) -> logging.Logger:
    """Returns logger for qget function.

    Args:
        debug (bool): Debug flag.

    Returns:
        logging.Logger: The configured logger.
    """
    logger = logging.getLogger("aio_download")
    logger.setLevel(logging.DEBUG if debug else logging.ERROR)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG if debug else logging.ERROR)
    logger.addHandler(handler)
    return logger


def _to_human_readable_unit(byte_count: int, out_format: str = "%.2f %s") -> str:
    """Returns byte count as human readable string.

    One of following units will be choosen: B, KB, MB, GB, TB.

    Args:
        byte_count (int): Byte count to convert.
        out_format (str, optional): Format of displayed unit. Defaults to "%.2f %s".

    Returns:
        str: The formatted string.
    """
    power = min(math.floor(math.log(byte_count, 1024)), len(_UNITS) - 1)
    divider = 1024**power
    return out_format % (byte_count / divider, _UNITS[power])


async def _test_connection(session: aiohttp.ClientSession, url: str) -> int:
    """Tests connection to given URL by creating streaming request and saves status code.
       Stream is keeped alive until cancellation of this coroutine.

    Args:
        session (aiohttp.ClientSession): Session that is used to create connections.
        url (str): The URL to be requested.

    Returns:
        int: Status code of performed request. Returns -1 if request was not performed successfully.
    """
    status_code = -1
    try:
        async with session.get(
            url,
            headers={
                "Accept": "*/*",
                "Range": "bytes=0-",
            },
            timeout=None,
        ) as response:
            status_code = response.status
            if status_code > 399:
                return status_code
            # To keep stream alive
            async for _ in response.content.iter_chunked(1):
                await asyncio.sleep(1)
    except (
        aiohttp.ClientResponseError,
        aiohttp.ClientConnectorError,
        asyncio.CancelledError,
    ):
        return status_code


async def _get_max_connections(url: str, pool: int, connection_test_sec: int, logger: logging.Logger = None) -> int:
    """Measures and returnes maximum amount of asynchronous HTTP connections to URL.

    Args:
        url (str): The URL to be requested.
        pool (int): The maximum connections amount provided by the user.
        connection_test_sec (int): Maximum time in seconds assigned to test
            how much asynchronous connections can be achieved to URL.
        logger (logging.Logger): Logger that will be used for debugging. Defaults to None.

    Returns:
        int: Number of asynchronous connections achieved.
    """
    connector = aiohttp.TCPConnector(limit=pool)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_test_connection(session, url) for _ in range(pool)]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=connection_test_sec)
        for task in pending:
            task.cancel()
        cancelled, _ = await asyncio.wait(pending)
        statuses = [task.result() for task in done] + [task.result() for task in cancelled]
        if logger:
            logger.debug("Test response status set: %s", set(statuses))
        return len([status for status in statuses if status > 0 and status < 400])


async def _get_resource_bytes(url: str) -> int:
    """Returns resource bytes from Content-Length header if possible.
       If HEAD request is not available for give resource URL, GET will be performed.

    Args:
        url (str): The resource URL to read size from.

    Returns:
        int: The resource bytes. Returns 0 if none of performed requests returns Content-Length header.

    Raises:
        ValueError: If server disconnects.
    """
    async with aiohttp.ClientSession() as session:
        try:
            response = await session.head(url)
            if response.status == 200 and "Content-Length" in response.headers:
                return int(response.headers.get("Content-Length"))
            raise ValueError("Content-Length not found for HEAD request")
        except (aiohttp.ServerDisconnectedError, ValueError):
            try:
                response = await session.get(url)
                if response.status == 200:
                    return int(response.headers.get("Content-Length", 0))
            except aiohttp.ServerDisconnectedError as ex:
                raise ValueError("Server disconnected") from ex
    return 0


def _validate_paths(filepath: str, override: bool, tmp_dir: str) -> None:
    """Validates paths settings. Raises error if some arguments are invalid.

    Args:
        See async def qget_coro(...).

    Raises:
        ValueError: If any argument has invalid value.
    """
    dirpath = os.path.dirname(filepath)
    if not os.path.isdir(dirpath):
        raise ValueError(f"Directory {dirpath} does not exists.")
    if not override and os.path.isfile(filepath):
        raise ValueError(f"File {filepath} already exists. Use override flag if it is intended behaviour.")
    if not os.path.isdir(tmp_dir):
        raise ValueError(f"Temporoary directory {tmp_dir} does not exists.")


def _validate_settings(max_connections: int, connection_test_sec: int, chunk_bytes: int, max_part_mb: float) -> None:
    """Validates download settings. Raises error if some arguments are invalid.

    Args:
        See async def qget_coro(...).

    Raises:
        ValueError: If any argument has invalid value.
    """
    if max_connections < 1:
        raise ValueError(f"Parameter max_connections has to have positive value. Actual value: {max_connections}.")
    if connection_test_sec < 0:
        raise ValueError(f"Parameter connection_test_sec cannot be negative. Actual value: {connection_test_sec}.")
    if chunk_bytes < 1:
        raise ValueError(f"Parameter chunk_bytes has to have positive value. Actual value: {chunk_bytes}.")
    if max_part_mb <= 0:
        raise ValueError(f"Parameter max_part_mb has to have positive value. Actual value: {max_part_mb}.")


async def _download_part(
    session: aiohttp.ClientSession,
    url: str,
    tmp_dir: str,
    part_data: PartData,
    chunk_bytes: int,
    progress_ref: ProgressState = None,
) -> None:
    """Downloads part of resource URL and stores it in temporary file.

    Args:
        session (aiohttp.ClientSession): Session that is used to create requests.
        url (str): The resource URL.
        tmp_dir (str): Temporary directory path to save part file.
        part_data (PartData): Basic informations about part.
        chunk_bytes (int): Chunk of data read in iteration from url and save to part file in bytes.
        progress_ref (ProgressState, optional): Reference to progress state.
            If passed part bytes will be updated in it. Defaults to None.
    """
    async with session.get(
        url,
        headers={
            "Accept": "*/*",
            "Range": f"bytes={part_data.begin}-{part_data.end}",
        },
        timeout=None,
    ) as response:
        async with aiofiles.open(f"{tmp_dir}/part-{part_data.part_id}.cr", "wb") as part_file:
            async for chunk in response.content.iter_chunked(chunk_bytes):
                await part_file.write(chunk)
                if progress_ref:
                    progress_ref.update_part_progress(part_data.part_id, len(chunk))


async def _rewrite_parts(filepath: str, tmp_dir: str, chunk_bytes: int, progress_ref: ProgressState = None) -> None:
    """Joins and removes all part files into output file.

    Args:
        filepath (str): Output path for joined file.
        tmp_dir (str): Temporary directory path that contains part files.
        chunk_bytes (int): Chunk of data read in iteration from part files and save to output file in bytes.
        progress_ref (ProgressState, optional): Reference to progress state.
            If passed rewrite status will be updated in it. Defaults to None.
    """
    rewrite_bytes = 0
    with open(filepath, "wb") as output_file:
        part_paths = sorted(glob.glob(f"{tmp_dir}/part-*.cr"))
        for part_path in part_paths:
            with open(part_path, "rb") as part_file:
                data = part_file.read(chunk_bytes)
                while data:
                    output_file.write(data)
                    rewrite_bytes += len(data)
                    if progress_ref:
                        progress_ref.update_rewrite_progress(rewrite_bytes)
                    data = part_file.read(chunk_bytes)
            os.remove(part_path)
    os.rmdir(tmp_dir)


async def qget_coro(
    url: str,
    filepath: str = None,
    override: bool = False,
    progress_ref: ProgressState = None,
    max_connections: int = 50,
    connection_test_sec: int = 5,
    chunk_bytes: int = 2621440,
    max_part_mb: float = 5.0,
    tmp_dir: str = None,
    debug: bool = False,
) -> None:
    """Download resource from given URL in buffered parts using asynchronous HTTP connections with aiohttp session.

    Args:
        url (str): The URL to download the resource.
        filepath (str, optional): Output path for downloaded resource.
            If not set it points to current working directory and filename from url. Defaults to None.
        override (bool, optional): Flag if existing output file should be override. Defaults to False.
        progress_ref (ProgressState, optional): Reference to progress state.
            If passed all parts bytes and rewrite status will be updated in it. Defaults to None.
        max_connections (int, optional): Maximum amount of asynchronous HTTP connections. Defaults to 50.
        connection_test_sec (int, optional): Maximum time in seconds assigned to test
            how much asynchronous connections can be achieved to URL. If set to 0 test will be omitted. Defaults to 5.
        chunk_bytes (int, optional): Chunk of data read in iteration from url and save to part file in bytes.
            Will be used also when rewriting parts to output file. Defaults to 2621440.
        max_part_mb (float, optional): Desirable (if possible) max part size in megabytes. Defaults to 5.
        tmp_dir (str, optional): Temporary directory path. If not set it points to OS tmp directory. Defaults to None.
        debug (bool, optional): Debug flag. Defaults to False.

    Raises:
        ValueError: If any argument has invalid value or server disconnects.
    """
    logger = _get_logger(debug)

    if filepath is None:
        filename = unquote(os.path.basename(urlparse(url).path))
        filepath = os.path.join(os.getcwd(), filename)
    if tmp_dir is None:
        tmp_dir = tempfile.gettempdir()

    _validate_paths(filepath, override, tmp_dir)
    _validate_settings(max_connections, connection_test_sec, chunk_bytes, max_part_mb)

    logger.debug("Fetching resource size...")
    resource_bytes = await _get_resource_bytes(url)
    if resource_bytes == 0:
        raise ValueError("Given URL does not support stream transfer or does not have Content-Length header provided.")
    if progress_ref:
        progress_ref.total_bytes = resource_bytes
    logger.debug("Resource size: %s", _to_human_readable_unit(resource_bytes))

    if connection_test_sec > 0:
        logger.debug("Measuring maximum asynchronous connections...")
        aio_connections = await _get_max_connections(url, max_connections, connection_test_sec, logger)
        if aio_connections == 0:
            raise ValueError("Cannot send any asynchronous connection to given resource URL.")
        logger.debug("Max connections set to: %d", aio_connections)
    else:
        logger.debug("Connection limit test: SKIPPED")
        aio_connections = max_connections
        logger.debug("Max connections set to: %d", aio_connections)

    tmp_dir = tempfile.mkdtemp(prefix="qget_parts-", dir=tmp_dir)
    logger.debug("Temporary parts path: %s", tmp_dir)

    semaphore = asyncio.Semaphore(aio_connections)

    async def _semaphore_task(task: asyncio.coroutine) -> asyncio.coroutine:
        """Executes tasks with use of semaphore."""
        async with semaphore:
            return await task

    connector = aiohttp.TCPConnector(limit=aio_connections)
    async with aiohttp.ClientSession(connector=connector) as session:
        part_bytes = min(math.ceil(resource_bytes / aio_connections), int(max_part_mb * 1024 * 1024))
        part_count = math.ceil(resource_bytes / part_bytes)
        logger.debug("Set parts as: %d x %s", part_count, _to_human_readable_unit(part_bytes))
        part_zfill = len(str(part_count))
        if progress_ref:
            progress_ref.init_parts_bytes(part_count, part_zfill)
        tasks = [
            _semaphore_task(
                _download_part(
                    session,
                    url,
                    tmp_dir,
                    PartData(
                        str(part).zfill(part_zfill),
                        begin,
                        resource_bytes if part == part_count - 1 else begin + part_bytes - 1,
                    ),
                    chunk_bytes,
                    progress_ref,
                )
            )
            for part, begin in enumerate(range(0, resource_bytes, part_bytes))
        ]

        logger.debug("Starting download...")
        download_start = round(time.time() * 1000)
        if progress_ref:
            progress_ref.download_start_timestamp_ms = download_start
        await asyncio.gather(*tasks)
        download_end = round(time.time() * 1000)
        if progress_ref:
            progress_ref.download_end_timestamp_ms = download_end
        logger.debug("Download finished in: %.2fs", (download_end - download_start) / 1000)

        logger.debug("Joining parts...")
        await _rewrite_parts(filepath, tmp_dir, chunk_bytes, progress_ref)
        join_end = round(time.time() * 1000)
        if progress_ref:
            progress_ref.rewrite_end_timestamp_ms = join_end
        logger.debug("Parts joined in: %.2fs", (join_end - download_end) / 1000)


def qget(url: str, **kwargs) -> None:
    """Calls asyncio coroutine to download resource from given url.

    To use own event loop please use ``qget_coro`` instead.

    Args:
        url (str): The URL to download the file.
        kwargs (**): Optional arguments that ``qget_coro`` takes.

    Keyword Args:
        filepath (str, optional): Output path for downloaded resource.
            If not set it points to current working directory and filename from url. Defaults to None.
        override (bool, optional): Flag if existing output file should be override. Defaults to False.
        progress_ref (ProgressState, optional): Reference to progress state.
            If passed all parts bytes and rewrite status will be updated in it. Defaults to None.
        max_connections (int, optional): Maximum amount of asynchronous HTTP connections. Defaults to 50.
        connection_test_sec (int, optional): Maximum time in seconds assigned to test
            how much asynchronous connections can be achieved to URL. If set to 0 test will be omitted. Defaults to 5.
        chunk_bytes (int, optional): Chunk of data read in iteration from url and save to part file in bytes.
            Will be used also when rewriting parts to output file. Defaults to 2621440.
        max_part_mb (float, optional): Desirable (if possible) max part size in megabytes. Defaults to 5.
        tmp_dir (str, optional): Temporary directory path. If not set it points to OS tmp directory. Defaults to None.
        debug (bool, optional): Debug flag. Defaults to False.
    """

    # Fix due to proactor event loop on Windows:
    # https://github.com/encode/httpx/issues/914
    if sys.version_info[0] == 3 and sys.version_info[1] >= 8 and sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.get_event_loop().run_until_complete(qget_coro(url, **kwargs))
