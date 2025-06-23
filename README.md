# Hanime Downloader

> A Python-based tool for downloading hanime from hanime.tv. This tool reads a list of URLs from a file and processes the downloads accordingly.

![Demo](https://github.com/Lysagxra/HanimeDownloader/blob/b461174a58539aefaf4fd305db2d58a0eedbf167/misc/Demo.gif)

## Features

- Downloads multiple files concurrently.
- Supports [batch downloading](https://github.com/Lysagxra/HanimeDownloader/tree/main?tab=readme-ov-file#batch-download) via a list of URLs.
- Tracks download progress with a progress bar.
- Automatically creates a directory structure for organized storage.

## Dependencies

- Python 3
- `httpx` - for HTTP requests with HTTP/1.1 & HTTP/2 support
- `m3u8` - for parsing and generating M3U8 playlists
- `pycryptodomex` - for encryption, decryption, and other cryptographic operations
- `rich` - for progress display in the terminal

## Directory Structure

```
project-root/
├── helpers/
│ ├── downloaders/
│ │ ├── crawler_utils.py       # Utilities for extracting media download links
│ │ └── episode_downloader.py  # Utilities for managing the download process
│ ├── managers/
│ │ ├── live_manager.py        # Manages a real-time live display
│ │ ├── log_manager.py         # Manages real-time log updates
│ │ └── progress_manager.py    # Manages progress bars
│ ├── config.py                # Manages constants and settings used across the project
│ ├── file_utils.py            # Utilities for managing file operations
│ └── general_utils.py         # Miscellaneous utility functions
├── hanime_downloader.py       # Module for initiating downloads from specified hanime.tv
├── main.py                    # Main script to run the downloader
└── URLs.txt                   # Text file listing album URLs to be downloaded
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Lysagxra/HanimeDownloader.git
```

2. Navigate to the project directory:

```bash
cd HanimeDownloader
```

3. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Single Album Download

To download a single album from an URL, you can use `hanime_downloader.py`, running the script with a valid album URL.

### Usage

```bash
python3 hanime_downloader.py <episode_url>
```

### Example

```
python3 hanime_downloader.py https://hanime.tv/videos/hentai/sukebe-elf-tanbouki-1
```

## Batch Download

To batch download from multiple album URLs, you can use the `main.py` script. This script reads URLs from a file named `URLs.txt` and downloads each one using the album downloader.

### Usage

1. Create a file named `URLs.txt` in the root of your project, listing each URL on a new line.

- Example of `URLs.txt`:

```
https://hanime.tv/videos/hentai/sukebe-elf-tanbouki-1
https://hanime.tv/videos/hentai/sukebe-elf-tanbouki-2
https://hanime.tv/videos/hentai/youkoso-sukebe-elf-no-mori-e-2
```

- Ensure that each URL is on its own line without any extra spaces.
- You can add as many URLs as you need, following the same format.

2. Run the batch download script:

```
python3 main.py
```

3. The downloaded files will be saved in the `Downloads` directory.


## Logging

The application logs any issues encountered during the download process.
