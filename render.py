import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

# ── Config ─────────────────────────────────────────────────────────────────────
TMP    = Path("/tmp/mlight")
TMP.mkdir(parents=True, exist_ok=True)

MLIGHT2_FOLDER = "1vXLbhQ-f4D-clk_NYxjHn6dhG7L8S7j5"
HI_FOLDER      = "1VYk8EYne8xGTAtwPdyUVoWOsBWJK7E35"
AD_FILE_ID     = "1GK27BbSSUcW5UHMtXqkSrVFcVcOXCDsa"
SUB_FILE_ID    = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"

AUDIO_BITRATE_K   = 128
MIN_SIZE_BYTES    = 1_000_000_000          # 1.00 GB
MAX_SIZE_BYTES    = int(1.98 * 1024 ** 3)  # 1.98 GB hard cap
TARGET_SIZE_BYTES = random.randint(
    int(1.00 * 1024 ** 3),
    int(1.93 * 1024 ** 3),                 # target up to 1.93 GB, cap stops at 1.98
)
DURATION        = random.randint(18000, 28800)
VIDEO_BITRATE_K = int((TARGET_SIZE_BYTES * 8) / DURATION / 1000)

TEXT = "buy our teddy bears in the first link in description"

TARGET_VIDEO_NAME = os.environ.get("TARGET_VIDEO_NAME", "").strip()
if not TARGET_VIDEO_NAME:
    raise SystemExit("[FATAL] TARGET_VIDEO_NAME env var is not set.")


# ── Helpers ────────────────────────────────────────────────────────────────────
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
        print(f"[SKIP] {label} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
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
            dest.unlink(missing_ok=True)
            print(f"[WARN] {label} empty after download, retrying...")
        except Exception as e:
            print(f"[WARN] {label} attempt {attempt} failed: {e}")
            dest.unlink(missing_ok=True)
            if attempt < retries:
                wait = 20 * attempt
                print(f"[WAIT] sleeping {wait}s...")
                time.sleep(wait)
    raise SystemExit(f"[FATAL] Could not download {label} after {retries} attempts.")


def download_folder(folder_id, dest_dir, label, retries=3, timeout=1800):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            print(f"[DL FOLDER] {label} — attempt {attempt}/{retries}")
            run_with_timeout(
                lambda: gdown.download_folder(id=folder_id, output=str(dest_dir), quiet=False),
                timeout_sec=timeout,
                label=label,
            )
            print(f"[OK] {label} folder downloaded.")
            return
        except Exception as e:
            print(f"[WARN] {label} attempt {attempt} failed: {e}")
            if attempt < retries:
                wait = 30 * attempt
                print(f"[WAIT] sleeping {wait}s...")
                time.sleep(wait)
    raise SystemExit(f"[FATAL] Could not download folder {label} after {retries} attempts.")


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
        raise SystemExit(f"[FATAL] Not enough disk — need {min_gb} GB, have {free_gb:.1f} GB")
    return free_gb


# ── Disk check ─────────────────────────────────────────────────────────────────
check_disk(TMP, 4.0, "before downloads")

# ── Download AD and SUB ────────────────────────────────────────────────────────
print("\n=== Downloading AD.mp4 ===")
ad_path = TMP / "AD.mp4"
download_file(AD_FILE_ID, ad_path, label="AD.mp4")

print("\n=== Downloading SUB.mp4 ===")
sub_path = TMP / "SUB.mp4"
download_file(SUB_FILE_ID, sub_path, label="SUB.mp4")

# ── Download songs ─────────────────────────────────────────────────────────────
print("\n=== Downloading hi (songs) folder ===")
songs_dir = TMP / "hi"
download_folder(HI_FOLDER, songs_dir, label="hi songs", timeout=900)

songs = sorted(p for p in songs_dir.rglob("*") if p.suffix.lower() == ".mp3")
if not songs:
    raise SystemExit("[FATAL] No .mp3 files found in hi folder.")
print(f"[INFO] Found {len(songs)} song(s).")

# ── Download target video ──────────────────────────────────────────────────────
print(f"\n=== Downloading mlight2 folder for: {TARGET_VIDEO_NAME} ===")
mlight2_dir = TMP / "mlight2"
download_folder(MLIGHT2_FOLDER, mlight2_dir, label="mlight2", timeout=1800)

matches = list(mlight2_dir.rglob(TARGET_VIDEO_NAME))
if not matches:
    raise SystemExit(f"[FATAL] {TARGET_VIDEO_NAME} not found in mlight2.")
video_path = matches[0]
print(f"[OK] Video: {video_path}")

# ── Probe SUB duration ─────────────────────────────────────────────────────────
SUB_DURATION = probe_duration(sub_path)
print(f"[INFO] SUB.mp4 duration: {SUB_DURATION:.2f}s")

# ── Song concat list ───────────────────────────────────────────────────────────
random.shuffle(songs)
concat_path = TMP / f"concat_{video_path.stem}.txt"
estimated_song_len = 200
repeats = max(1, (DURATION // (len(songs) * estimated_song_len)) + 2)
with open(concat_path, "w") as f:
    for _ in range(repeats):
        batch = songs[:]
        random.shuffle(batch)
        for s in batch:
            f.write(f"file '{s}'\n")
print(f"[INFO] Song list: {len(songs)} tracks x {repeats} repeats.")

# ── SUB overlay schedule (every 5-10 min) ─────────────────────────────────────
sub_appearances = []
t = random.randint(300, 600)
while t < DURATION - SUB_DURATION - 10:
    end_t    = round(t + SUB_DURATION, 2)
    position = random.choice(["bl", "br"])
    sub_appearances.append((t, end_t, position))
    t += random.randint(300, 600)

sub_bl = [(s, e) for s, e, p in sub_appearances if p == "bl"]
sub_br = [(s, e) for s, e, p in sub_appearances if p == "br"]

def make_enable(intervals):
    if not intervals:
        return "0"
    return "+".join(f"between(t,{s},{e})" for s, e in intervals)

enable_sub_bl = make_enable(sub_bl)
enable_sub_br = make_enable(sub_br)
print(f"[INFO] SUB: {len(sub_bl)} bottom-left, {len(sub_br)} bottom-right")

# ── AD overlay schedule (every 4-8 min) ───────────────────────────────────────
AD_SHOW_DUR = 10
ad_appearances = []
t = random.randint(240, 480)
while t < DURATION - AD_SHOW_DUR - 10:
    end_t    = t + AD_SHOW_DUR
    position = random.choice(["bl", "br"])
    ad_appearances.append((t, end_t, position))
    t += random.randint(240, 480)

ad_bl = [(s, e) for s, e, p in ad_appearances if p == "bl"]
ad_br = [(s, e) for s, e, p in ad_appearances if p == "br"]

enable_ad_bl = make_enable(ad_bl)
enable_ad_br = make_enable(ad_br)
print(f"[INFO] AD: {len(ad_bl)} bottom-left, {len(ad_br)} bottom-right")

# ── Output ─────────────────────────────────────────────────────────────────────
output_path = TMP / f"OUT_{video_path.stem}.mp4"

print(f"""
=== RENDER JOB ===
  VIDEO         : {video_path.name}
  SONGS         : {len(songs)} tracks (randomized, looped)
  DURATION      : {DURATION}s  ({DURATION//3600}h {(DURATION%3600)//60}m)
  TARGET SIZE   : {TARGET_SIZE_BYTES / 1e9:.2f} GB
  HARD CAP      : {MAX_SIZE_BYTES / 1e9:.2f} GB  (1.98 GB)
  VIDEO BITRATE : {VIDEO_BITRATE_K}k
  SUB           : {len(sub_appearances)} appearances every 5-10 min
  AD            : {len(ad_appearances)} appearances every 4-8 min
""")

check_disk(TMP, 2.0, "after downloads")

# ── Filter graph ───────────────────────────────────────────────────────────────
filter_complex = (
    # Scale main video to 1920x1080, 30fps
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[base];"

    # SUB: remove green screen, scale to 22% width
    "[1:v]chromakey=0x00FF00:0.25:0.1,scale=iw*0.22:-1[sub_clean];"
    "[sub_clean]split[sub_bl][sub_br];"

    # SUB bottom-left
    f"[base][sub_bl]overlay=30:H-h-30:enable='{enable_sub_bl}'[v1];"
    # SUB bottom-right
    f"[v1][sub_br]overlay=W-w-30:H-h-30:enable='{enable_sub_br}'[v2];"

    # AD: scale to 280px wide
    "[2:v]scale=280:-1[ad_clean];"
    "[ad_clean]split[ad_bl][ad_br];"

    # AD bottom-left
    f"[v2][ad_bl]overlay=30:H-h-30:enable='{enable_ad_bl}'[v3];"
    # AD bottom-right
    f"[v3][ad_br]overlay=W-w-30:H-h-30:enable='{enable_ad_br}'[v4];"

    # Text overlay — fades in/out every 60s
    "[v4]drawtext="
    "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    f"text='{TEXT}':"
    "fontcolor=white:fontsize=42:"
    "alpha='if(lt(mod(t,60),2),mod(t,60)/2,"
    "if(lt(mod(t,60),7),1,"
    "if(lt(mod(t,60),9),(9-mod(t,60))/2,0)))':"
    "x=(w-text_w)/2:y=h-text_h-60[outv]"
)

# ── FFmpeg ─────────────────────────────────────────────────────────────────────
cmd = [
    "ffmpeg", "-y", "-hide_banner", "-fflags", "+genpts",
    "-stream_loop", "-1", "-i", str(video_path),   # [0] main video
    "-stream_loop", "-1", "-i", str(sub_path),      # [1] SUB
    "-stream_loop", "-1", "-i", str(ad_path),       # [2] AD
    "-f", "concat", "-safe", "0", "-i", str(concat_path),  # [3] audio
    "-filter_complex", filter_complex,
    "-map", "[outv]",
    "-map", "3:a",
    "-af", "volume=0.8",
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

print("=== Starting FFmpeg ===")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

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
                print("[SIZE] Reached 1.98 GB cap — stopping FFmpeg.", flush=True)
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

# ── Validate ───────────────────────────────────────────────────────────────────
if not stopped_by_watcher and proc.returncode not in (0, 255):
    raise SystemExit(f"[FATAL] FFmpeg exited with code {proc.returncode}")

if not output_path.exists():
    raise SystemExit("[FATAL] Output file does not exist.")

final_size = output_path.stat().st_size
if final_size == 0:
    raise SystemExit("[FATAL] Output file is 0 bytes.")

final_size_mb = final_size / (1024 ** 2)
final_size_gb = final_size / (1024 ** 3)
stop_reason   = "size cap (1.98 GB)" if stopped_by_watcher else "duration reached"

# ── Size check — must be 1 GB to 1.98 GB ──────────────────────────────────────
if final_size < MIN_SIZE_BYTES:
    raise SystemExit(
        f"[FATAL] Output only {final_size_gb:.3f} GB — below 1 GB minimum. "
        f"Video may be too short or bitrate too low."
    )

print(f"""
=== RENDER COMPLETE ===
  Output        : {output_path}
  Stop reason   : {stop_reason}
  Final size    : {final_size_mb:.1f} MB  ({final_size_gb:.3f} GB)
  Size OK       : {'✅ YES' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else '❌ OUT OF RANGE'}
  Bitrate used  : {VIDEO_BITRATE_K}k
  SUB           : {len(sub_appearances)} appearances (5-10 min intervals)
  AD            : {len(ad_appearances)} appearances (4-8 min intervals)
  Source video  : {video_path.name}
""")

# ── GitHub Actions outputs ─────────────────────────────────────────────────────
github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"video_name={video_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"video_bitrate_k={VIDEO_BITRATE_K}\n")
        f.write(f"stop_reason={stop_reason}\n")
