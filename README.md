# M3U8 Video Downloader

## Introduction
This is a Python script designed to download and merge M3U8 videos. It supports multiple methods to find the M3U8 link from the playback page, including regular expression matching, BeautifulSoup parsing, and iframe analysis. The script also supports multi-threaded downloading and two methods for merging video segments: simple binary merging and using `ffmpeg`.

## Features
- Automatically find the M3U8 link from the playback page.
- Support for multi-threaded downloading to improve efficiency.
- Retry mechanism for failed downloads.
- Automatically select the highest quality stream if multiple options are available.
- Two methods for merging video segments: simple binary merging and using `ffmpeg`.

## Installation
1. Clone this repository to your local machine:
```bash
git clone https://github.com/olelukcie/m3u8-video-downloader.git
cd m3u8-video-downloader
```
2. Install the required Python packages:
```bash
pip install requests m3u8 beautifulsoup4
```
3. If you want to use the `ffmpeg` merging method, you need to install `ffmpeg` on your system. You can download it from the [official website](https://ffmpeg.org/download.html).

## Usage
```bash
python m3u8_downloader.py [URL] [OPTIONS]
```

### Options
- `URL`: Video playback page URL or M3U8 link.
- `-o, --output`: Output file name. Default is `output.mp4`.
- `-d, --directory`: Download directory. Default is `downloaded_video`.
- `-w, --workers`: Number of concurrent download threads. Default is 10.
- `-r, --retries`: Number of retries on download failure. Default is 3.
- `-q, --quiet`: Quiet mode, do not display progress.

### Example
```bash
python m3u8_downloader.py https://example.com/video-playback-page -o my_video.mp4 -d my_downloads -w 20 -r 5 -q
```

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contributing
If you have any suggestions or find any bugs, please feel free to open an issue or submit a pull request.

## Disclaimer
This script is for educational and research purposes only. Please respect the copyright of the video content and do not use it for illegal activities.