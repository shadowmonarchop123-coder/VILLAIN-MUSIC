import asyncio
import glob
import json
import os
import random
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Union
import string
import requests
import yt_dlp
import aiohttp  # Added for fallback API
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from py_yt import VideosSearch, CustomSearch
import base64
from PritiMusic import LOGGER
from PritiMusic.utils.database import is_on_off
from PritiMusic.utils.formatters import time_to_seconds
from config import YT_API_KEY, YTPROXY_URL as YTPROXY

logger = LOGGER(__name__)

def cookie_txt_file():
    try:
        folder_path = f"{os.getcwd()}/cookies"
        filename = f"{os.getcwd()}/cookies/logs.csv"
        txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
        if not txt_files:
            raise FileNotFoundError("No .txt files found in the specified folder.")
        cookie_txt_file = random.choice(txt_files)
        with open(filename, 'a') as file:
            file.write(f'Choosen File : {cookie_txt_file}\n')
        return f"""cookies/{str(cookie_txt_file).split("/")[-1]}"""
    except:
        return None


async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.dl_stats = {
            "total_requests": 0,
            "okflix_downloads": 0,
            "cookie_downloads": 0,
            "existing_files": 0
        }


    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]


        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
            
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        if "?si=" in link:
            link = link.split("?si=")[0]
        elif "&si=" in link:
            link = link.split("&si=")[0]

        try:
            results = []
            search = VideosSearch(link, limit=10)
            search_results = (await search.next()).get("result", [])

            for result in search_results:
                duration_str = result.get("duration", "0:00")
                try:
                    parts = duration_str.split(":")
                    duration_secs = 0
                    if len(parts) == 3:
                        duration_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    elif len(parts) == 2:
                        duration_secs = int(parts[0]) * 60 + int(parts[1])

                    if duration_secs <= 3600:
                        results.append(result)
                except (ValueError, IndexError):
                    continue

            if not results or query_type >= len(results):
                raise ValueError("No suitable videos found within duration limit")

            selected = results[query_type]
            return (
                selected["title"],
                selected["duration"],
                selected["thumbnails"][0]["url"].split("?")[0],
                selected["id"]
            )

        except Exception as e:
            LOGGER(__name__).error(f"Error in slider: {str(e)}")
            raise ValueError("Failed to fetch video details")

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            vid_id = link
            link = self.base + link
        loop = asyncio.get_running_loop()

        # FALLBACK API LOGIC MERGED HERE
        async def fallback_dl(vid_id, filepath, dl_type="audio"):
            API_URL = "https://shrutibots.site"
            os.makedirs("downloads", exist_ok=True)
            
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filepath
                
            try:
                async with aiohttp.ClientSession() as session:
                    params = {"url": vid_id, "type": dl_type}
                    async with session.get(f"{API_URL}/download", params=params, timeout=aiohttp.ClientTimeout(total=7)) as response:
                        if response.status != 200: 
                            return None
                        
                        data = await response.json()
                        download_token = data.get("download_token")
                        if not download_token: 
                            return None
                        
                        stream_url = f"{API_URL}/stream/{vid_id}?type={dl_type}&token={download_token}"
                        async with session.get(stream_url, timeout=aiohttp.ClientTimeout(total=300)) as file_response:
                            if file_response.status == 302:
                                redirect_url = file_response.headers.get('Location')
                                if redirect_url:
                                    async with session.get(redirect_url) as final_resp:
                                        if final_resp.status == 200:
                                            with open(filepath, "wb") as f:
                                                async for chunk in final_resp.content.iter_chunked(16384):
                                                    f.write(chunk)
                            elif file_response.status == 200:
                                with open(filepath, "wb") as f:
                                    async for chunk in file_response.content.iter_chunked(16384):
                                        f.write(chunk)
                                        
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
            except Exception as e:
                logger.error(f"Fallback {dl_type} download failed: {str(e)}")
                if os.path.exists(filepath):
                    try: os.remove(filepath)
                    except: pass
            return None

        def create_session():
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.1)
            session.mount('http://', HTTPAdapter(max_retries=retries))
            session.mount('https://', HTTPAdapter(max_retries=retries))
            return session

        async def download_with_requests(url, filepath, headers=None):
            try:
                session = create_session()
                response = session.get(
                    url, 
                    headers=headers, 
                    stream=True, 
                    timeout=60,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                downloaded = 0
                chunk_size = 1024 * 1024
                
                with open(filepath, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            file.write(chunk)
                            downloaded += len(chunk)
                
                return filepath
                
            except Exception as e:
                logger.error(f"Requests download failed: {str(e)}")
                if os.path.exists(filepath):
                    os.remove(filepath)
                return None
            finally:
                session.close()

        async def audio_dl(vid_id):
            filepath = os.path.join("downloads", f"{vid_id}.mp3")
            
            try:
                if not YT_API_KEY or not YTPROXY:
                    logger.warning("API KEY or YTPROXY not set in config. Triggering fallback API.")
                    return await fallback_dl(vid_id, filepath, "audio")
                
                headers = {
                    "x-api-key": f"{YT_API_KEY}",
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "X-Audio-Quality": "high",
                    "X-Format-Preference": "opus,m4a,mp3",
                    "X-Bitrate-Preference": "256,192,128",
                    "X-Enhance-Audio": "true"
                }
                
                if os.path.exists(filepath):
                    return filepath
                
                session = create_session()
                audio_params = {
                    "enhance_audio": "true",
                    "prefer_bitrate": "256",
                    "optimize_for_voice_chat": "true",
                    "include_metadata": "true",
                    "normalize_audio": "true",
                    "preserve_bass": "true"
                }
                
                getAudio = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, params=audio_params, timeout=60)
                songData = getAudio.json()
                session.close()
                
                if songData.get('status') == 'success':
                    audio_url = songData['audio_url']
                    if 'audio_qualities' in songData:
                        qualities = songData['audio_qualities']
                        for quality in ['256kbps', '192kbps', '128kbps', 'high', 'medium']:
                            if quality in qualities:
                                audio_url = qualities[quality]
                                break
                    
                    audio_url += '&enhance=true&normalize=true&preserve_bass=true' if '?' in audio_url else '?enhance=true&normalize=true&preserve_bass=true'
                    result = await download_with_requests(audio_url, filepath, headers)
                    
                    if result:
                        return result

            except Exception as e:
                logger.error(f"Error in primary proxy audio download: {str(e)}")
                
            # If everything above fails, use fallback
            logger.info(f"Using fallback API for audio {vid_id}")
            return await fallback_dl(vid_id, filepath, "audio")
        
        async def video_dl(vid_id):
            filepath = os.path.join("downloads", f"{vid_id}.mp4")
            
            try:
                if not YT_API_KEY or not YTPROXY:
                    logger.warning("API KEY or YTPROXY not set in config. Triggering fallback API.")
                    return await fallback_dl(vid_id, filepath, "video")
                
                headers = {"x-api-key": f"{YT_API_KEY}", "User-Agent": "Mozilla/5.0"}
                
                if os.path.exists(filepath):
                    return filepath
                
                session = create_session()
                getVideo = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, timeout=60)
                videoData = getVideo.json()
                session.close()
                
                if videoData.get('status') == 'success':
                    video_url = videoData['video_url']
                    result = await download_with_requests(video_url, filepath, headers)
                    if result:
                        return result
                        
            except Exception as e:
                logger.error(f"Error in primary proxy video download: {str(e)}")
            
            # Use fallback if failed
            logger.info(f"Using fallback API for video {vid_id}")
            return await fallback_dl(vid_id, filepath, "video")
        
        async def song_video_dl():
            filepath = f"downloads/{title}.mp4"
            try:
                if not YT_API_KEY or not YTPROXY:
                    logger.warning("API KEY or YTPROXY not set in config. Triggering fallback API.")
                    return await fallback_dl(vid_id, filepath, "video")
                
                headers = {"x-api-key": f"{YT_API_KEY}", "User-Agent": "Mozilla/5.0"}
                if os.path.exists(filepath): return filepath
                
                session = create_session()
                getVideo = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, timeout=60)
                videoData = getVideo.json()
                session.close()
                
                if videoData.get('status') == 'success':
                    video_url = videoData['video_url']
                    result = await download_with_requests(video_url, filepath, headers)
                    if result: return result
                    
            except Exception as e:
                logger.error(f"Error in primary song video download: {str(e)}")
                
            # Use fallback if failed
            logger.info(f"Using fallback API for song video {title}")
            return await fallback_dl(vid_id, filepath, "video")

        async def song_audio_dl():
            filepath = f"downloads/{title}.mp3"
            try:
                if not YT_API_KEY or not YTPROXY:
                    logger.warning("API KEY or YTPROXY not set in config. Triggering fallback API.")
                    return await fallback_dl(vid_id, filepath, "audio")
                
                headers = {
                    "x-api-key": f"{YT_API_KEY}",
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "X-Audio-Quality": "premium",
                    "X-Format-Preference": "opus,m4a,mp3",
                    "X-Bitrate-Preference": "320,256,192",
                    "X-Enhance-Audio": "true",
                    "X-Audio-Enhancement": "bass_boost+normalize+cleaning"
                }
                
                if os.path.exists(filepath): return filepath
                
                session = create_session()
                audio_params = {
                    "enhance_audio": "true",
                    "prefer_bitrate": "320",
                    "optimize_for_voice_chat": "true",
                    "include_metadata": "true",
                    "normalize_audio": "true",
                    "preserve_bass": "true",
                    "enhance_clarity": "true",
                    "dynamic_range": "wide",
                    "audio_profile": "telegram_optimized"
                }
                
                getAudio = session.get(f"{YTPROXY}/info/{vid_id}", headers=headers, params=audio_params, timeout=60)
                audioData = getAudio.json()
                session.close()
                
                if audioData.get('status') == 'success':
                    audio_url = audioData['audio_url']
                    if 'enhanced_audio_url' in audioData:
                        audio_url = audioData['enhanced_audio_url']
                    elif 'audio_qualities' in audioData:
                        for quality_key, quality_url in audioData['audio_qualities'].items():
                            if '320' in quality_key or 'highest' in quality_key.lower():
                                audio_url = quality_url
                                break
                    
                    audio_url += '&enhance=true&normalize=true&bass_boost=true&cleaning=true' if '?' in audio_url else '?enhance=true&normalize=true&bass_boost=true&cleaning=true'
                    result = await download_with_requests(audio_url, filepath, headers)
                    
                    if result: return result
                    
            except Exception as e:
                logger.error(f"Error in primary song audio download: {str(e)}")
                
            # Use fallback if failed
            logger.info(f"Using fallback API for song audio {title}")
            return await fallback_dl(vid_id, filepath, "audio")

        if songvideo:
            fpath = await song_video_dl()
            return fpath
        elif songaudio:
            fpath = await song_audio_dl()
            return fpath
        elif video:
            direct = True
            downloaded_file = await video_dl(vid_id)
        else:
            direct = True
            downloaded_file = await audio_dl(vid_id)
        
        return downloaded_file, direct
