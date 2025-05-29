import requests
import m3u8
import os
import re
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class M3U8VideoDownloader:
    """M3U8 Video Downloader Class"""
    
    def __init__(self, url, output_dir="downloaded_video", output_file="output.mp4", 
                 max_workers=10, retry_times=3, timeout=15, quiet=False):
        """Initialize the downloader"""
        self.url = url
        self.output_dir = output_dir
        self.output_file = output_file
        self.max_workers = max_workers
        self.retry_times = retry_times
        self.timeout = timeout
        self.quiet = quiet
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        self.total_segments = 0
        self.completed_segments = 0
        self.start_time = 0
        
    def log(self, message):
        """Log output"""
        if not self.quiet:
            print(message)
            
    def error(self, message):
        """Error output"""
        print(f"[Error] {message}")
            
    def find_m3u8_url(self):
        """Find the m3u8 link from the playback page"""
        self.log(f"Analyzing the playback page: {self.url}")
        
        try:
            # Add Referer header to simulate browser behavior
            self.headers['Referer'] = self.url
            response = requests.get(self.url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Method 1: Use regular expressions to directly find the m3u8 link
            m3u8_pattern = r'(https?://[^\s\'\"<>\(\)]+\.m3u8)'
            matches = re.findall(m3u8_pattern, response.text)
            if matches:
                m3u8_url = matches[0]
                self.log(f"Found m3u8 link: {m3u8_url}")
                return m3u8_url
            
            # Method 2: Use BeautifulSoup to parse the page
            soup = BeautifulSoup(response.text, 'html.parser')
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    if '.m3u8' in script.string:
                        # Try to extract the m3u8 link from JavaScript code
                        matches = re.findall(m3u8_pattern, script.string)
                        if matches:
                            m3u8_url = matches[0]
                            self.log(f"Found m3u8 link from script tag: {m3u8_url}")
                            return m3u8_url
            
            # Method 3: Analyze embedded iframes
            iframe_tags = soup.find_all('iframe')
            for iframe in iframe_tags:
                src = iframe.get('src')
                if src:
                    iframe_url = urljoin(self.url, src)
                    self.log(f"Found iframe: {iframe_url}, trying to analyze...")
                    # Recursively find the m3u8 link in the iframe
                    self.url = iframe_url
                    return self.find_m3u8_url()
            
            self.error("Could not find the m3u8 link on the page")
            return None
            
        except Exception as e:
            self.error(f"Failed to analyze the playback page: {e}")
            return None
    
    def download_ts(self, ts_url, output_path, retry=0):
        """Download a single TS segment"""
        try:
            if retry > 0:
                self.log(f"Retrying to download {ts_url} ({retry}/{self.retry_times})")
            
            response = requests.get(ts_url, headers=self.headers, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunk
                    if chunk:
                        f.write(chunk)
            
            self.completed_segments += 1
            elapsed = time.time() - self.start_time
            speed = self.completed_segments / elapsed if elapsed > 0 else 0
            eta = (self.total_segments - self.completed_segments) / speed if speed > 0 else 0
            
            progress = f"\rProgress: {self.completed_segments}/{self.total_segments} "
            progress += f"[{(self.completed_segments/self.total_segments)*100:.2f}%] "
            progress += f"Speed: {speed:.2f} segments/sec "
            progress += f"ETA: {eta//60:.0f} min {eta%60:.0f} sec"
            
            if not self.quiet:
                print(progress, end='', flush=True)
            
            return True
            
        except Exception as e:
            if retry < self.retry_times:
                time.sleep(1 + retry)  # Exponential backoff
                return self.download_ts(ts_url, output_path, retry + 1)
            else:
                self.error(f"Failed to download {ts_url}: {e}")
                return False
    
    def check_and_download_missing_segments(self, ts_urls):
        """Check and download missing segments"""
        missing_segments = []
        for ts_url, index in ts_urls:
            output_path = os.path.join(self.output_dir, f"segment_{index}.ts")
            if not os.path.exists(output_path):
                missing_segments.append((ts_url, index))
        
        if missing_segments:
            self.log(f"Found {len(missing_segments)} missing segments, starting download...")
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for ts_url, index in missing_segments:
                    output_path = os.path.join(self.output_dir, f"segment_{index}.ts")
                    futures.append(executor.submit(self.download_ts, ts_url, output_path))
                
                # Wait for all downloads to complete
                for future in as_completed(futures):
                    future.result()  # Get the result and trigger exceptions
            
            # Recursively check if there are still missing segments
            self.check_and_download_missing_segments(ts_urls)
    
    def download_m3u8_video(self, m3u8_url=None):
        """Download and merge M3U8 videos"""
        if not m3u8_url:
            if '.m3u8' in self.url:
                m3u8_url = self.url
            else:
                m3u8_url = self.find_m3u8_url()
                if not m3u8_url:
                    self.error("Could not obtain the m3u8 link")
                    return False
        
        self.log(f"Parsing the M3U8 file: {m3u8_url}")
        
        try:
            # Add Referer header
            self.headers['Referer'] = urljoin(m3u8_url, '/')
            
            response = requests.get(m3u8_url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the m3u8 file
            m3u8_obj = m3u8.loads(response.text)
            
            # Create the save directory
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            
            # Handle nested m3u8 files
            if m3u8_obj.is_variant:
                # Select the highest quality stream
                playlists = sorted(m3u8_obj.playlists, 
                                  key=lambda p: p.stream_info.bandwidth or 0, 
                                  reverse=True)
                
                self.log("Found multiple quality options:")
                for i, playlist in enumerate(playlists):
                    resolution = playlist.stream_info.resolution
                    bandwidth = playlist.stream_info.bandwidth / 1000000 if playlist.stream_info.bandwidth else "Unknown"
                    self.log(f"  {i+1}. Resolution: {resolution}, Bandwidth: {bandwidth:.2f} Mbps")
                
                # Automatically select the highest quality
                selected = playlists[0]
                self.log(f"Selected the highest quality: {selected.stream_info.resolution or 'Unknown'}")
                
                playlist_url = selected.uri
                if not playlist_url.startswith(('http:', 'https:')):
                    playlist_url = urljoin(m3u8_url, playlist_url)
                
                return self.download_m3u8_video(playlist_url)
            
            # Extract all TS segments
            base_url = m3u8_url.rsplit('/', 1)[0] + '/'
            ts_urls = []
            
            for i, segment in enumerate(m3u8_obj.segments):
                ts_url = segment.uri
                if not ts_url.startswith(('http:', 'https:')):
                    ts_url = urljoin(base_url, ts_url)
                ts_urls.append((ts_url, i))
            
            self.total_segments = len(ts_urls)
            self.completed_segments = 0
            self.start_time = time.time()
            
            if self.total_segments == 0:
                self.error("No video segments found")
                return False
            
            self.log(f"Found a total of {self.total_segments} video segments")
            self.log("Starting download...")
            
            # Multi-threaded download
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for ts_url, index in ts_urls:
                    output_path = os.path.join(self.output_dir, f"segment_{index}.ts")
                    futures.append(executor.submit(self.download_ts, ts_url, output_path))
                
                # Wait for all downloads to complete
                for future in as_completed(futures):
                    future.result()  # Get the result and trigger exceptions
            
            print()  # New line
            
            # Check and download missing segments
            self.check_and_download_missing_segments(ts_urls)
            
            self.log("All segments downloaded, starting to merge...")
            
            # Merge all TS files
            output_path = os.path.join(self.output_dir, self.output_file)
            
            # Method 1: Simple binary merge (suitable for most cases)
            try:
                with open(output_path, 'wb') as outfile:
                    for i in range(self.total_segments):
                        segment_path = os.path.join(self.output_dir, f"segment_{i}.ts")
                        if os.path.exists(segment_path):
                            with open(segment_path, 'rb') as infile:
                                outfile.write(infile.read())
                        else:
                            self.error(f"Warning: Segment {i} does not exist")
                
                self.log(f"Video merged successfully: {output_path}")
                return True
                
            except Exception as e:
                self.error(f"Simple merge failed: {e}")
                self.error("Trying a more professional merge method...")
                
                # Method 2: Use ffmpeg to merge (ffmpeg needs to be installed)
                try:
                    import subprocess
                    
                    # Generate the merge list file
                    list_file = os.path.join(self.output_dir, "filelist.txt")
                    with open(list_file, 'w') as f:
                        for i in range(self.total_segments):
                            segment_path = os.path.join(self.output_dir, f"segment_{i}.ts")
                            if os.path.exists(segment_path):
                                f.write(f"file '{segment_path.replace(os.sep, '/')}'\n")
                    
                    # Execute the ffmpeg command
                    cmd = [
                        'ffmpeg', 
                        '-f', 'concat', 
                        '-safe', '0', 
                        '-i', list_file, 
                        '-c', 'copy', 
                        output_path
                    ]
                    
                    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self.log(f"Merged using ffmpeg successfully: {output_path}")
                    return True
                    
                except Exception as e:
                    self.error(f"ffmpeg merge failed: {e}")
                    self.error("Please try to merge the segments manually")
                    return False
                    
        except Exception as e:
            self.error(f"An error occurred during the download: {e}")
            return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='M3U8 Video Downloader')
    parser.add_argument('url', help='Video playback page URL or m3u8 link')
    parser.add_argument('-o', '--output', default='output.mp4', help='Output file name')
    parser.add_argument('-d', '--directory', default='downloaded_video', help='Download directory')
    parser.add_argument('-w', '--workers', type=int, default=10, help='Number of concurrent download threads')
    parser.add_argument('-r', '--retries', type=int, default=3, help='Number of retries on download failure')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode, do not display progress')
    
    args = parser.parse_args()
    
    downloader = M3U8VideoDownloader(
        url=args.url,
        output_dir=args.directory,
        output_file=args.output,
        max_workers=args.workers,
        retry_times=args.retries,
        quiet=args.quiet
    )
    
    success = downloader.download_m3u8_video()
    if success:
        print("\n✅ Download successful!")
    else:
        print("\n❌ Download failed!")

if __name__ == "__main__":
    main()