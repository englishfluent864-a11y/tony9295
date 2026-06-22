import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP             = Path("/tmp/mlight")
DURATION        = random.randint(18000, 28800)
AUDIO_BITRATE_K = 128
TEXT            = "buy our teddy bears in the first link in description"

MIN_SIZE_BYTES    = 1_000_000_000
MAX_SIZE_BYTES    = int(1.99 * 1024 ** 3)
TARGET_SIZE_BYTES = random.randint(MIN_SIZE_BYTES, int(1.85 * 1024 ** 3))
VIDEO_BITRATE_K   = int((TARGET_SIZE_BYTES * 8) / DURATION / 1000)

SUB_INTERVAL = random.randint(360, 840)
SUB_DURATION = random.randint(3, 4)
SUB_POSITION = random.choice(["left", "right"])
SUB_X        = "40" if SUB_POSITION == "left" else "W-w-40"

MUSIC_TRACK = random.randint(1, 5)

FILES = {
    "1.mp3":   "13Mv43VyBzfVTf6pq0q6CH4-CspKR60t7",
    "2.mp3":   "1TCtVi_uQhLPbaZoKVnjOVdAYsjm6NJf9",
    "3.mp3":   "1Y236Yr4z_THsypDe9pn1SPtRRv20-ERD",
    "4.mp3":   "1KhPnbvK1690od9H3QqPq4wsRifE3mY42",
    "5.mp3":   "17FltDNodKR-5fkqSsZR_W6dr-_MFx49J",
    "AD.mp4":  "1GK27BbSSUcW5UHMtXqkSrVFcVcOXCDsa",
    "SUB.mp4": "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw",
}

MLIGHT2_FOLDER    = "1vXLbhQ-f4D-clk_NYxjHn6dhG7L8S7j5"
TARGET_VIDEO_NAME = os.environ.get("TARGET_VIDEO_NAME")
TARGET_VIDEO_ID   = os.environ.get("TARGET_VIDEO_ID")

if not TARGET_VIDEO_NAME:
    raise SystemExit("TARGET_VIDEO_NAME env var not set.")

# ── Timeout helper ────────────────────────────────────────────────────────────
def download_with_timeout(fn, timeout_sec=1800, label="download"):
    result = [None]
    error  = [None]
    def worker():
        try:
            result[0] = fn()
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError(f"{label} timed out after {timeout_sec}s")
    if error[0]:
        raise error[0]
    return result[0]

# ── Setup dirs ────────────────────────────────────────────────────────────────
TMP.mkdir(exist_ok=True)
(TMP / "mlight2").mkdir(exist_ok=True)

# ── Disk space check ──────────────────────────────────────────────────────────
stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free space: {free_gb:.1f} GB")
if free_gb < 4.0:
    raise SystemExit(f"[DISK] Not enough free space ({free_gb:.1f} GB). Need at least 4 GB.")

# ── Download static assets ────────────────────────────────────────────────────
for name, fid in FILES.items():
    dest = TMP / name
    if dest.exists():
        print(f"Skipping {name} (already downloaded)")
        continue
    print(f"Downloading {name}...")
    try:
        download_with_timeout(
            lambda fid=fid, dest=dest: gdown.download(id=fid, output=str(dest), quiet=False),
            timeout_sec=600, label=name
        )
    except Exception as e:
        raise SystemExit(f"Failed to download {name}: {e}")

# ── Download target video ─────────────────────────────────────────────────────
mlight2_dir = TMP / "mlight2"
video_path  = mlight2_dir / TARGET_VIDEO_NAME

if TARGET_VIDEO_ID:
    print(f"Downloading target video by ID: {TARGET_VIDEO_NAME}")
    try:
        download_with_timeout(
            lambda: gdown.download(id=TARGET_VIDEO_ID, output=str(video_path), quiet=False),
            timeout_sec=1800, label=TARGET_VIDEO_NAME
        )
    except Exception as e:
        raise SystemExit(f"Failed to download target video: {e}")
else:
    print(f"No VIDEO_ID provided, downloading whole folder to find: {TARGET_VIDEO_NAME}")
    try:
        download_with_timeout(
            lambda: gdown.download_folder(id=MLIGHT2_FOLDER, output=str(mlight2_dir), quiet=False),
            timeout_sec=1800, label="mlight2 folder"
        )
    except Exception as e:
        raise SystemExit(f"Failed to download mlight2 folder: {e}")
    matches = list(mlight2_dir.rglob(TARGET_VIDEO_NAME))
    if not matches:
        raise SystemExit(f"Target video {TARGET_VIDEO_NAME} not found after download.")
    video_path = matches[0]

if not video_path.exists():
    raise SystemExit(f"Video file not found: {video_path}")

music_file  = TMP / f"{MUSIC_TRACK}.mp3"
output_path = TMP / f"OUT_{video_path.stem}.mp4"

print(f"\n>>> VIDEO        : {video_path.name}")
print(f">>> MUSIC        : {music_file.name} (track {MUSIC_TRACK}, looped)")
print(f">>> DURATION     : {DURATION}s ({DURATION//3600}h {(DURATION%3600)//60}m)")
print(f">>> TARGET SIZE  : {TARGET_SIZE_BYTES / 1e9:.2f} GB")
print(f">>> VIDEO BITRATE: {VIDEO_BITRATE_K}k")
print(f">>> SUB INTERVAL : every {SUB_INTERVAL}s ({SUB_INTERVAL//60}m {SUB_INTERVAL%60}s), visible {SUB_DURATION}s")
print(f">>> SUB POSITION : bottom-{SUB_POSITION} (x={SUB_X})\n")

# ── Disk check after downloads ────────────────────────────────────────────────
stat = os.statvfs(str(TMP))
free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
print(f"[DISK] Free after downloads: {free_gb:.1f} GB")
if free_gb < 2.0:
    raise SystemExit(f"[DISK] Not enough space to render ({free_gb:.1f} GB free).")

# ── Filter graph ──────────────────────────────────────────────────────────────
filter_complex = (
    "[0:v]scale=1920:1080,fps=30,format=yuv420p[base];"
    "[2:v]chromakey=0x00FF00:0.25:0.1,scale=iw*0.30:-1[sub];"
    f"[base][sub]overlay={SUB_X}:H-h-40:enable='lt(mod(t,{SUB_INTERVAL}),{SUB_DURATION})'[v1];"
    "[3:v]scale=320:-1[ad];"
    "[v1][ad]overlay=W-w-20:H-h-20:enable='between(mod(t,300),0,10)'[v2];"
    "[v2]drawtext="
    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    f"text='{TEXT}':"
    "fontcolor=white:fontsize=42:"
    "alpha='if(lt(mod(t,60),2),mod(t,60)/2,if(lt(mod(t,60),7),1,(9-mod(t,60))/2))':"
    "x=(w-text_w)/2:y=h-text_h-60[outv]"
)

# ── FFmpeg command ────────────────────────────────────────────────────────────
cmd = [
    "ffmpeg", "-y", "-fflags", "+genpts",
    "-stream_loop", "-1", "-i", str(video_path),
    "-stream_loop", "-1", "-i", str(music_file),
    "-stream_loop", "-1", "-i", str(TMP / "SUB.mp4"),
    "-stream_loop", "-1", "-i", str(TMP / "AD.mp4"),
    "-filter_complex", filter_complex,
    "-map", "[outv]", "-map", "1:a",
    "-t", str(DURATION),
    "-c:v", "libx264", "-preset", "ultrafast",
    "-b:v", f"{VIDEO_BITRATE_K}k",
    "-bufsize", f"{VIDEO_BITRATE_K * 2}k",
    "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_K}k", "-ar", "44100",
    "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
    "-profile:v", "high", "-level", "4.1",
    "-movflags", "+faststart",
    str(output_path),
]

# ── Run FFmpeg with live output + size watcher ────────────────────────────────
print("Running FFmpeg...")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

stopped_by_watcher = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(15)
        if output_path.exists():
            size = output_path.stat().st_size
            mb   = size / (1024 * 1024)
            gb   = size / (1024 * 1024 * 1024)
            print(f"[SIZE] {output_path.name} → {mb:.1f} MB ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] ⚠️  Hit 1.99 GB cap — stopping FFmpeg cleanly.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                break

watcher = threading.Thread(target=size_watcher, daemon=True)
watcher.start()

for line in proc.stdout:
    print(line, end="", flush=True)

proc.wait()
watcher.join()

if not stopped_by_watcher and proc.returncode != 0:
    raise SystemExit(f"FFmpeg failed with exit code {proc.returncode}")

if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("Output file missing after FFmpeg.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 * 1024)
final_size_gb = final_size / (1024 * 1024 * 1024)
stop_reason   = "capped at 1.99 GB by size watcher" if stopped_by_watcher else "duration reached"

if final_size < MIN_SIZE_BYTES:
    print(f"[WARN] Output is only {final_size_gb:.3f} GB — below the 1 GB minimum target.")

print(f"\nDONE — {output_path}")
print(f"Stop reason  : {stop_reason}")
print(f"Bitrate used : {VIDEO_BITRATE_K}k")
print(f"Sub interval : {SUB_INTERVAL}s, visible {SUB_DURATION}s, position: bottom-{SUB_POSITION}")
print(f"Audio track  : {music_file.name} (looped)")
print(f"Size         : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)")
print(f"Video        : {video_path.name}")

# ── Write outputs for workflow ────────────────────────────────────────────────
github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"video_name={video_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"video_bitrate_k={VIDEO_BITRATE_K}\n")
