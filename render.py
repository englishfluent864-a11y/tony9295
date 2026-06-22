import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP              = Path("/tmp/mlight")
AUDIO_BITRATE_K  = 128
TEXT             = "buy our teddy bears in the first link in description"

MIN_SIZE_BYTES    = 1_000_000_000
MAX_SIZE_BYTES    = int(1.90 * 1024 ** 3)
TARGET_SIZE_BYTES = random.randint(MIN_SIZE_BYTES, int(1.85 * 1024 ** 3))

DURATION = random.randint(18000, 28800)

VIDEO_BITRATE_K = int((TARGET_SIZE_BYTES * 8) / DURATION / 1000)

SUB_INTERVAL = 240
AD_INTERVAL  = 300
AD_DURATION  = 10

SUB_POSITION = random.choice(["bottom_left", "top_left"])

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
TARGET_VIDEO_NAME = os.environ.get("TARGET_VIDEO_NAME", "").strip()
TARGET_VIDEO_ID   = os.environ.get("TARGET_VIDEO_ID",   "").strip()

if not TARGET_VIDEO_NAME:
    raise SystemExit("[FATAL] TARGET_VIDEO_NAME env var is not set.")

# ── Helpers ───────────────────────────────────────────────────────────────────

def run_with_timeout(fn, timeout_sec=1800, label="operation"):
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
        raise TimeoutError(f"[TIMEOUT] {label} exceeded {timeout_sec}s")
    if error[0]:
        raise error[0]
    return result[0]


def download_file(file_id, dest, label, retries=3, timeout=600):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[SKIP] {label} already downloaded ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    for attempt in range(1, retries + 1):
        try:
            print(f"[DL] {label} — attempt {attempt}/{retries}")
            run_with_timeout(
                lambda: gdown.download(id=file_id, output=str(dest), quiet=False),
                timeout_sec=timeout,
                label=label,
            )
            if dest.exists() and dest.stat().st_size > 0:
                print(f"[OK] {label} — {dest.stat().st_size / 1e6:.1f} MB")
                return
            else:
                print(f"[WARN] {label} — file empty after download, retrying…")
                dest.unlink(missing_ok=True)
        except Exception as e:
            print(f"[WARN] {label} attempt {attempt} failed: {e}")
            dest.unlink(missing_ok=True)
            if attempt < retries:
                wait = 20 * attempt
                print(f"[WAIT] sleeping {wait}s before retry…")
                time.sleep(wait)
    raise SystemExit(f"[FATAL] Could not download {label} after {retries} attempts.")


def probe_duration(path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
        return float(out)
    except Exception as e:
        print(f"[WARN] ffprobe failed on {path}: {e} — defaulting to 5s")
        return 5.0


def check_disk(path, min_gb, label="disk check"):
    stat    = os.statvfs(str(path))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
    print(f"[DISK] {label}: {free_gb:.1f} GB free")
    if free_gb < min_gb:
        raise SystemExit(f"[FATAL] Not enough disk space — need {min_gb} GB, have {free_gb:.1f} GB")
    return free_gb


# ── Setup ─────────────────────────────────────────────────────────────────────
TMP.mkdir(parents=True, exist_ok=True)
check_disk(TMP, 4.0, "before downloads")

# ── Download static assets ────────────────────────────────────────────────────
print("\n=== Downloading static assets ===")
for name, fid in FILES.items():
    download_file(fid, TMP / name, label=name)

# ── Download target video ─────────────────────────────────────────────────────
print(f"\n=== Downloading target video: {TARGET_VIDEO_NAME} ===")
mlight2_dir = TMP / "mlight2"
mlight2_dir.mkdir(parents=True, exist_ok=True)
video_path  = mlight2_dir / TARGET_VIDEO_NAME

if TARGET_VIDEO_ID:
    download_file(TARGET_VIDEO_ID, video_path, label=TARGET_VIDEO_NAME,
                  retries=3, timeout=1800)
else:
    print("[INFO] No TARGET_VIDEO_ID — downloading full folder to locate file…")
    for attempt in range(1, 4):
        try:
            run_with_timeout(
                lambda: gdown.download_folder(
                    id=MLIGHT2_FOLDER,
                    output=str(mlight2_dir),
                    quiet=False,
                ),
                timeout_sec=1800,
                label="mlight2 folder",
            )
            break
        except Exception as e:
            print(f"[WARN] Folder download attempt {attempt} failed: {e}")
            if attempt == 3:
                raise SystemExit("[FATAL] Could not download mlight2 folder after 3 attempts.")
            time.sleep(30 * attempt)
    matches = list(mlight2_dir.rglob(TARGET_VIDEO_NAME))
    if not matches:
        raise SystemExit(f"[FATAL] {TARGET_VIDEO_NAME} not found in downloaded folder.")
    video_path = matches[0]

if not video_path.exists() or video_path.stat().st_size == 0:
    raise SystemExit(f"[FATAL] Video file missing or empty: {video_path}")

# ── Probe SUB.mp4 real duration ───────────────────────────────────────────────
sub_file     = TMP / "SUB.mp4"
SUB_DURATION = probe_duration(sub_file)
print(f"[INFO] SUB.mp4 real duration: {SUB_DURATION:.2f}s")

music_file  = TMP / f"{MUSIC_TRACK}.mp3"
output_path = TMP / f"OUT_{video_path.stem}.mp4"

if SUB_POSITION == "bottom_left":
    sub_x = "40"
    sub_y = "H-h-40"
else:
    sub_x = "40"
    sub_y = "40"

print(f"""
=== RENDER JOB ===
  VIDEO        : {video_path.name}
  MUSIC        : {music_file.name} (track {MUSIC_TRACK}, looped, 80% vol)
  DURATION     : {DURATION}s  ({DURATION//3600}h {(DURATION%3600)//60}m)
  TARGET SIZE  : {TARGET_SIZE_BYTES / 1e9:.2f} GB
  HARD CAP     : {MAX_SIZE_BYTES / 1e9:.2f} GB
  VIDEO BITRATE: {VIDEO_BITRATE_K}k
  SUB INTERVAL : every {SUB_INTERVAL}s, plays {SUB_DURATION:.1f}s
  SUB POSITION : {SUB_POSITION} (x={sub_x}, y={sub_y})
  AD INTERVAL  : every {AD_INTERVAL}s, plays {AD_DURATION}s
""")

check_disk(TMP, 2.0, "after downloads")

# ── Filter graph ──────────────────────────────────────────────────────────────
filter_complex = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[base];"

    "[2:v]chromakey=0x00FF00:0.25:0.1,scale=iw*0.30:-1[sub];"

    f"[base][sub]overlay={sub_x}:{sub_y}:"
    f"enable='lt(mod(t,{SUB_INTERVAL}),{SUB_DURATION:.2f})'[v1];"

    "[3:v]scale=320:-1[ad];"
    f"[v1][ad]overlay=W-w-20:H-h-20:"
    f"enable='between(mod(t,{AD_INTERVAL}),0,{AD_DURATION})'[v2];"

    "[v2]drawtext="
    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    f"text='{TEXT}':"
    "fontcolor=white:fontsize=42:"
    "alpha='if(lt(mod(t,60),2),mod(t,60)/2,"
    "if(lt(mod(t,60),7),1,"
    "if(lt(mod(t,60),9),(9-mod(t,60))/2,0)))':"
    "x=(w-text_w)/2:y=h-text_h-60[outv]"
)

audio_filter = "volume=0.8"

# ── FFmpeg command ────────────────────────────────────────────────────────────
cmd = [
    "ffmpeg", "-y", "-hide_banner", "-fflags", "+genpts",
    "-stream_loop", "-1", "-i", str(video_path),
    "-stream_loop", "-1", "-i", str(music_file),
    "-stream_loop", "-1", "-i", str(sub_file),
    "-stream_loop", "-1", "-i", str(TMP / "AD.mp4"),
    "-filter_complex", filter_complex,
    "-map", "[outv]",
    "-map", "1:a",
    "-af", audio_filter,
    "-t", str(DURATION),
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-b:v", f"{VIDEO_BITRATE_K}k",
    "-bufsize", f"{VIDEO_BITRATE_K * 2}k",
    "-maxrate", f"{int(VIDEO_BITRATE_K * 1.2)}k",
    "-c:a", "aac",
    "-b:a", f"{AUDIO_BITRATE_K}k",
    "-ar", "44100",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "-g", "60",
    "-profile:v", "high",
    "-level", "4.1",
    "-movflags", "+faststart",
    str(output_path),
]

# ── Run FFmpeg ────────────────────────────────────────────────────────────────
print("=== Starting FFmpeg ===")
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

stopped_by_watcher = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(10)
        if output_path.exists():
            size = output_path.stat().st_size
            mb   = size / (1024 ** 2)
            gb   = size / (1024 ** 3)
            print(f"[SIZE] {mb:.0f} MB  ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Reached 1.90 GB cap — stopping FFmpeg.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break

watcher_thread = threading.Thread(target=size_watcher, daemon=True)
watcher_thread.start()

for line in proc.stdout:
    print(line, end="", flush=True)

proc.wait()
watcher_thread.join(timeout=30)

# ── Validate output ───────────────────────────────────────────────────────────
if not stopped_by_watcher and proc.returncode not in (0, 255):
    raise SystemExit(f"[FATAL] FFmpeg exited with code {proc.returncode}")

if not output_path.exists():
    raise SystemExit("[FATAL] Output file does not exist after render.")

final_size = output_path.stat().st_size
if final_size == 0:
    raise SystemExit("[FATAL] Output file is 0 bytes.")

final_size_mb = final_size / (1024 ** 2)
final_size_gb = final_size / (1024 ** 3)
stop_reason   = "size cap (1.90 GB)" if stopped_by_watcher else "duration reached"

if final_size < MIN_SIZE_BYTES:
    print(f"[WARN] Output is {final_size_gb:.3f} GB — below the 1 GB minimum.")

print(f"""
=== RENDER COMPLETE ===
  Output       : {output_path}
  Stop reason  : {stop_reason}
  Final size   : {final_size_mb:.1f} MB  ({final_size_gb:.3f} GB)
  Bitrate used : {VIDEO_BITRATE_K}k
  Audio track  : {music_file.name} (80% volume, looped)
  SUB interval : every {SUB_INTERVAL}s, plays {SUB_DURATION:.1f}s, pos: {SUB_POSITION}
  AD interval  : every {AD_INTERVAL}s, plays {AD_DURATION}s
  Source video : {video_path.name}
""")

# ── GitHub Actions outputs ────────────────────────────────────────────────────
github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"video_name={video_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"video_bitrate_k={VIDEO_BITRATE_K}\n")
        f.write(f"stop_reason={stop_reason}\n")
