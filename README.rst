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

.. contents:: **Table of Contents**

Features
========

- an executable script to download file via command line
- support for HTTPS connection with basic auth and SSL verification skip
- support for custom headers
- automatic measurement of simultaneous connections limit
- support for limiting download rate
- support for retries during part downloading
- support for downloading / rewriting progress with callbacks (by default using ``tqdm``)
- support for limiting RAM usage with settings ``chunk_bytes`` and ``max_part_mb``
- support for using own event loop in ``asyncio`` by ``qget_coro`` coroutine
- support for SOCKS4(a), SOCKS5(h), HTTP (tunneling) proxy

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


Now let's compare download statistics for ``wget`` and ``qget`` for **1000MB** file and configuration
mentioned above:

+-------------+----------------+------------------+-------------------------------+
| Application | Total time [s] | AVG Speed [MB/s] | Details                       |
+=============+================+==================+===============================+
| ``wget``    | 251.34         | 3.98             |                               |
+-------------+----------------+------------------+-------------------------------+
|| ``qget``   || 16.00         || 95.97           || Connection limit test: 5.00s |
||            ||               ||                 || Download: 10.42s             |
||            ||               ||                 || Parts rewrite: 0.58s         |
+-------------+----------------+------------------+-------------------------------+

**Conclusion**:

For simple rate limiting (*per connection*) ``qget`` allows to achieve **multiple times faster** download speed
based on user internet connection speed, number of simultaneous requests and resource server configuration.
In example above ``qget`` achieved over **24x** download speed of ``wget``.

For more complicated cases (*e.g. connections limit per IP*) automatic connection limit measurement test was
created to calculate how many simultaneous requests could be achieved before server rejects next one.

Requirements
============

- `Python <https://www.python.org/>`_ >= 3.7
- `aiohttp <https://pypi.org/project/aiohttp/>`_
- `aiofiles <https://pypi.org/project/aiofiles/>`_
- `aiohttp-socks <https://pypi.org/project/aiohttp-socks/>`_
- `tqdm <https://pypi.org/project/tqdm/>`_

Installation
============

You can download selected binary files from `Releases <https://github.com/dwojtasik/qget/releases/latest>`_.
Available versions:

- Windows 32-bit (qget-|latest_version|-win32.exe)
- Windows 64-bit (qget-|latest_version|-win_amd64.exe)
- POSIX 32-bit (qget-|latest_version|-i386)
- POSIX 64-bit (qget-|latest_version|-amd64)

To install ``qget`` module, simply:

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
  proxy_url (str, optional): HTTP/SOCKS4/SOCKS5 proxy url in format 'protocol://user:password@ip:port'.
      Defaults to None.
  headers: (Dict[str, str], optional): Custom headers to be sent. Default to None.
      If set user can specify own User-Agent and Accept headers, otherwise defaults will be used.
  progress_ref (ProgressState, optional): Reference to progress state.
      If passed all parts bytes and rewrite status will be updated in it. Defaults to None.
  max_connections (int, optional): Maximum amount of asynchronous HTTP connections. Defaults to 50.
  connection_test_sec (int, optional): Maximum time in seconds assigned to test
      how much asynchronous connections can be achieved to URL.
      If set to 0 test will be omitted. Defaults to 5.
  chunk_bytes (int, optional): Chunk of data read in iteration from url and save to part file in bytes.
      Will be used also when rewriting parts to output file. If limit is supplied this can be override for
      stream iteration. Defaults to 2621440.
  max_part_mb (float, optional): Desirable (if possible) max part size in megabytes. Defaults to 5.
  retries (int, optional): Retries number for part download. Defaults to 10.
  retry_sec (int, optional): Time to wait between retries of part download in seconds. Defaults to 1.
  limit (str, optional): Download rate limit in MBps. Can be supplied with unit as "Nunit", eg. "5M".
      Valid units (case insensitive): b, k, m, g, kb, mb, gb. 0 bytes will be treat as no limit.
      Defaults to None.
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

To use in code with own loop and ``asyncio``:

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

Progress hooks
**************

Usage for progress hooks (by default hooks are used to display ``tqdm`` progress bar):

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

  usage: qget [-h] [-o FILEPATH] [-f] [-a AUTH] [--no-verify] [--no-mock]
              [--proxy PROXY_URL] [-H HEADER] [-c MAX_CONNECTIONS]
              [--test CONNECTION_TEST_SEC] [--bytes CHUNK_BYTES] [--part MAX_PART_MB]
              [--retries RETRIES] [--retry_sec RETRY_SEC] [--limit LIMIT] [--tmp TMP_DIR]
              [--debug] [-v]
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
    --no-verify           Disables SSL certificate validation.
    --no-mock             Disables default User-Agent header.
    --proxy PROXY_URL     HTTP/SOCKS4/SOCKS5 proxy url in format
                          'protocol://user:password@ip:port'.
    -H HEADER, --header HEADER
                          Custom header in format 'name:value'. Can be supplied multiple
                          times.
    -c MAX_CONNECTIONS, --connections MAX_CONNECTIONS
                          Maximum amount of asynchronous HTTP connections.
    --test CONNECTION_TEST_SEC
                          Maximum time in seconds assigned to test how much asynchronous
                          connections can be achieved to URL. Use 0 to skip.
    --bytes CHUNK_BYTES   Chunk of data read in iteration from url and save to part file in
                          bytes. Will be used also when rewriting parts to output file.
    --part MAX_PART_MB    Desirable (if possible) max part size in megabytes.
    --retries RETRIES     Retries number for part download.
    --retry_sec RETRY_SEC Time to wait between retries of part download in seconds.
    --limit LIMIT         Download rate limit in MBps. Can be supplied with unit as 'Nunit',
                          eg. '5M'. Valid units (case insensitive): b, k, m, g, kb, mb, gb.
                          0 bytes will be treat as no limit.
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

Notes
=====
Limiter
-------
Limiter tries to reduce rate of downloaded bytes by adding pauses between iteration over resource content.
If very low download rate is requested try to lower connections amount (``max_connections`` or ``--connections
MAX_CONNECTIONS``) to achieve better accuracy for limit.

Part size
---------
Part size is calculated in runtime based on resource size in bytes and maximum amount of asynchronous
connections set by user (or connection test). Max part size param (``max_part_mb`` or ``--part MAX_PART_MB``)
supplied by user is use as a top limit for calculated value.

.. code-block:: text

   part_bytes = min(resource_bytes/connections, max_part_bytes)

History
=======
0.1.7 (2023-05-15)
------------------
- Added retries and retry_sec parameter validation.

0.1.6 (2023-05-15)
------------------
- Fixed multiple logging handlers created with multiple qget calls.
- Added retries for connection errors during async downloading.

0.1.5 (2023-01-25)
------------------
- Updated copyright note.

0.1.4 (2022-08-25)
------------------
- Added support for SOCKS4(a), SOCKS5(h), HTTP (tunneling) proxy.
- Added argument position mixing for command line usage.

0.1.1 (2022-06-09)
------------------
- Added rate limiter with multiple unit support.
- Added version flag for command line usage.
- Renamed --no-ssl flag to --no-verify.

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

.. |latest_version| replace:: 0.1.7