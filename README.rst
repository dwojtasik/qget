==================================
qget - Async http(s) downloader
==================================

.. image:: https://img.shields.io/pypi/v/qget.svg
   :target: https://pypi.org/project/qget
   :alt: Latest PyPI package version

.. image:: https://img.shields.io/pypi/pyversions/qget.svg?logo=python&logoColor=white
   :target: https://pypi.org/project/qget
   :alt: Python supported versions

.. image:: https://img.shields.io/pypi/l/qget.svg
   :target: https://raw.githubusercontent.com/dwojtasik/qget/main/LICENSE
   :alt: License

**qget** is an Apache2 licensed library, written in Python, for downloading web
resources in asynchronous manner as fast as possible.

Under the hood it benefits from ``asyncio`` and ``aiohttp`` to create multiple
simultaneous connections to resource and download it using buffered part files.

Features
========

- an executable script to download file via command line
- support for HTTPS connection with basic auth and SSL verification skip
- support for custom headers
- support for downloading / rewriting progress with callbacks (by default using ``tqdm``)
- support for limiting RAM usage with settings ``chunk_bytes`` and ``max_part_mb``
- automatic measurement of simultaneous connection limit
- support for using own event loop in asyncio by ``qget_coro`` coroutine

Motivation: ``wget`` vs ``qget``
================================
Consider simple ``nginx`` configuration fragment like this:

.. code-block:: nginx

  http {
      server {
          ...
          limit_rate   5m;
          ...
      }
  }


Now let's compare download statistics for ``wget`` and ``qget`` for **1000MB** file and above configuration:

+-------------+----------------+------------------+-------------------------------+
| Application | Total time [s] | AVG Speed [MB/s] | Details                       |
+=============+================+==================+===============================+
| ``wget``    | 251.34         | 3.98             |                               |
+-------------+----------------+------------------+-------------------------------+
|| ``qget``   || 16.00         || 95.97           || Connection limit test: 5.00s |
||            ||               ||                 || Download: 10.42s             |
||            ||               ||                 || Parts rewrite: 0.58s         |
+-------------+----------------+------------------+-------------------------------+

|
| **Conclusion**:
| For simple rate limiting (*per connection*) ``qget`` allows to achieve **multiple times faster** download speed
| based on user internet connection speed, number of simultaneous requests and resource server configuration.
| In example above ``qget`` achived over **24x** download speed of ``wget``.

For more complicated cases (*e.g. connections limit per IP*) automatic connection limit measurement test was
created to calculate how many simultaneous requests could be achieved before server rejects next one.

Requirements
============

- Python >= 3.7
- `aiohttp <https://pypi.org/project/aiohttp/>`_
- `aiofiles <https://pypi.org/project/aiofiles/>`_
- `tqdm <https://pypi.org/project/tqdm/>`_

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

.. code-block:: text

  url (str): The URL to download the resource.
  filepath (str, optional): Output path for downloaded resource.
      If not set it points to current working directory and filename from url. Defaults to None.
  override (bool, optional): Flag if existing output file should be override. Defaults to False.
  auth (str, optional): String of user:password pair for SSL connection. Defaults to None.
  verify_ssl (bool, optional): Flag if SSL certificate validation should be performed. Defaults to True.
  mock_browser (bool, optional): Flag if User-Agent header should be added to request. Defaults to True.
      Default User-Agent string: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
      (KHTML, like Gecko) Chrome/101.0.4951.67 Safari/537.36'
  headers: (Dict[str, str], optional): Custom headers to be sent. Default to None.
      If set user can specify own User-Agent and Accept headers, otherwise defaults will be used.
  progress_ref (ProgressState, optional): Reference to progress state.
      If passed all parts bytes and rewrite status will be updated in it. Defaults to None.
  max_connections (int, optional): Maximum amount of asynchronous HTTP connections. Defaults to 50.
  connection_test_sec (int, optional): Maximum time in seconds assigned to test
      how much asynchronous connections can be achieved to URL.
      If set to 0 test will be omitted. Defaults to 5.
  chunk_bytes (int, optional): Chunk of data read in iteration from url and save to part file in bytes.
      Will be used also when rewriting parts to output file. Defaults to 2621440.
  max_part_mb (float, optional): Desirable (if possible) max part size in megabytes. Defaults to 5.
  tmp_dir (str, optional): Temporary directory path. If not set it points to OS tmp directory.
      Defaults to None.
  debug (bool, optional): Debug flag. Defaults to False.

|

To use in code simply import module function:

.. code-block:: python

  from qget import qget

  url = "https://speed.hetzner.de/100MB.bin"
  qget(url)

|

To use in code with own loop and **asyncio**:

.. code-block:: python

  import asyncio
  from qget import qget_coro

  async def main(loop):
      url = "https://speed.hetzner.de/100MB.bin"
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

  url = "https://speed.hetzner.de/100MB.bin"
  progress = ProgressState(
    on_download_progress=print_download_progress,
    on_rewrite_progress=print_rewrite_progress
  )
  qget(url, progress_ref=progress)

Command line
------------

.. code-block:: text

  usage: qget [-h] [-o FILEPATH] [-f] [-a AUTH] [--no-ssl] [--no-mock] [-H HEADER]
              [-c MAX_CONNECTIONS] [--test CONNECTION_TEST_SEC] [--bytes CHUNK_BYTES]
              [--part MAX_PART_MB] [--tmp TMP_DIR] [--debug] [-v]
              url

  Downloads resource from given URL in buffered parts using asynchronous HTTP connections
  with aiohttp session.

  positional arguments:
    url                   URL of resource

  options:
    -h, --help            show this help message and exit
    -o FILEPATH, --output FILEPATH
                          Output path for downloaded resource.
    -f, --force           Forces file override for output.
    -a AUTH, --auth AUTH  String of user:password pair for SSL connection.
    --no-ssl              Disables SSL certificate validation.
    --no-mock             Disables default User-Agent header.
    -H HEADER, --header HEADER
                          Custom header in format 'name:value'.
    -c MAX_CONNECTIONS, --connections MAX_CONNECTIONS
                          Maximum amount of asynchronous HTTP connections.
    --test CONNECTION_TEST_SEC
                          Maximum time in seconds assigned to test how much asynchronous
                          connections can be achieved to URL. Use 0 to skip.
    --bytes CHUNK_BYTES   Chunk of data read in iteration from url and save to part file in
                          bytes. Will be used also when rewriting parts to output file.
    --part MAX_PART_MB    Desirable (if possible) max part size in megabytes.
    --tmp TMP_DIR         Temporary directory path. If not set it points to OS tmp
                          directory.
    --debug               Debug flag.
    -v, --version         Displays actual version of qget.

|

Can be used also from python module with same arguments as for binary:

.. code-block:: bash

  python -m qget https://speed.hetzner.de/100MB.bin

|

Multiple headers can be supplied as follow:

.. code-block:: bash

  python -m qget -H 'name1:value1' -H 'name2:value2' https://speed.hetzner.de/100MB.bin

History
=======
NEXT / DEV
------------------
- Added version flag for command line usage.

0.0.8 (2022-06-04)
------------------
- Added User-Agent mock settings.
- Added custom headers support.
- Fixed auth validation.
- Fixed error messages in validation.
- Changed command line arguments for flags (used '-' instead of '_').

0.0.6 (2022-05-31)
------------------
- Added HTTPS support.
- Fixed fallback to GET request on failed HEAD Content-Length read.
- Fixed binary build scripts.

0.0.1 (2022-05-31)
------------------
- Initial version.