==================================
qget - Async http downloader
==================================

**qget** is an Apache2 licensed library, written in Python, for downloading web
resources in asynchronous manner as fast as possible.

Under the hood it benefits from ``asyncio`` and ``aiohttp`` to create multiple
simultaneous connections to resource and download it using buffered part files.

Features
========

- an executable script to download file via command line
- support for downloading / rewriting progress with callbacks (by default using ``tqdm``)
- support for using own event loop in asyncio by qget_coro coroutine
- support for limiting RAM usage with settings ``chunk_bytes`` and ``max_part_mb``
- automatic measurement of simultaneous connection limit

Installation
============

You can download selected binary file from Releases. Available versions:

- Windows 32/64-bit
- POSIX 32/64-bit

To install **qget** module, simply:

.. code-block:: bash

    $ pip install qget

Build
=====

Make sure `Anaconda <https://www.anaconda.com/>`_ is installed.

To build on **Windows** (in Anaconda Prompt):

.. code-block:: powershell

    $ build.bat

To build on **POSIX** (``libc-bin`` and ``binutils`` packages are required):

.. code-block:: bash

    $ build.sh

Usage
=====

Python code
-----------
Function arguments:

.. code-block:: python

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

|

To use in code simply import module function:

.. code-block:: python

  from qget import qget

  url = "https://proof.ovh.net/files/100Mb.dat"
  qget(url)

|

To use in code with own loop and **asyncio**:

.. code-block:: python

  import asyncio
  from qget import qget_coro

  async def main(loop):
      url = "https://proof.ovh.net/files/100Mb.dat"
      download_task = loop.create_task(qget_coro(url))
      await download_task
      # Or just
      # await qget_coro(url)

  loop = asyncio.get_event_loop()
  loop.run_until_complete(main(loop))
  loop.close()

|

Usage for progress hooks (by default hooks are used to display **tqdm** progress bar):

.. code-block:: python

  from qget import ProgressState, qget

  def print_download_progress(progress: ProgressState) -> None:
      print(f"Download: {progress.get_download_progress():.2f}%", end="\r")
      if progress.get_download_bytes() == progress.total_bytes:
          print()

  def print_rewrite_progress(progress: ProgressState) -> None:
      print(f"Rewrite: {progress.get_rewrite_progress():.2f}%", end="\r")
      if progress.rewrite_bytes == progress.total_bytes:
          print()

  url = "https://proof.ovh.net/files/100Mb.dat"
  progress = ProgressState(
    on_download_progress=print_download_progress,
    on_rewrite_progress=print_rewrite_progress
  )
  qget(url, progress_ref=progress)


Command line
------------

.. code-block:: bash

  usage: qget [-h] [-o FILEPATH] [-f] [-c MAX_CONNECTIONS] [--test CONNECTION_TEST_SEC] [--bytes CHUNK_BYTES]
                [--part MAX_PART_MB] [--tmp TMP_DIR] [--debug]
                url

  Downloads resource from given URL in buffered parts using asynchronous HTTP connections with aiohttp session.

  positional arguments:
    url                   URL of resource

  options:
    -h, --help            show this help message and exit
    -o FILEPATH, --output FILEPATH
                          Output path for downloaded resource.
    -f, --force           Forces file override for output.
    -c MAX_CONNECTIONS, --connections MAX_CONNECTIONS
                          Maximum amount of asynchronous HTTP connections.
    --test CONNECTION_TEST_SEC
                          Maximum time in seconds assigned to test how much asynchronous connectionscan be achieved to
                          URL. Use 0 to skip.
    --bytes CHUNK_BYTES   Chunk of data read in iteration from url and save to part file in bytes. Will be used also
                          when rewriting parts to output file.
    --part MAX_PART_MB    Desirable (if possible) max part size in megabytes.
    --tmp TMP_DIR         Temporary directory path. If not set it points to OS tmp directory.
    --debug               Debug flag.

|

Can be used also from python module with same arguments as for binary:

.. code-block:: bash

  python -m qget https://proof.ovh.net/files/100Mb.dat

History
=======
0.0.1 (2022-05-31)
------------------
- Initial version.