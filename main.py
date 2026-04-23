from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import Optional
import base64
import subprocess
import tempfile
import os
import json

app = FastAPI()

BG_COLOR_DEFAULT   = os.getenv("BG_COLOR",    "#000000")
TEXT_COLOR_DEFAULT = os.getenv("TEXT_COLOR",  "#FFFFFF")
FONT_DEFAULT       = os.getenv("FONT",        "Montserrat")
FONT_SIZE_DEFAULT  = os.getenv("FONT_SIZE",   "80")
BOLD_DEFAULT       = os.getenv("BOLD",        "1")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc.errors())})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {str(exc)}"})


def hex_to_ass(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def to_ass_time(sec: float) -> str:
    h  = int(sec // 3600)
    m  = int((sec % 3600) // 60)
    s  = sec % 60
    cs = min(int(round((s % 1) * 100)), 99)
    return f"{h}:{m:02d}:{int(s):02d}.{cs:02d}"


def build_ass(transcript, text_color, font, font_size, bold) -> str:
    primary = hex_to_ass(text_color)
    outline  = hex_to_ass("#000000")

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font},{font_size},{primary},&H000000FF,"
        f"{outline},&H00000000,{bold},0,0,0,100,100,0,0,1,4,0,5,80,80,200,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines = ""
    for item in transcript:
        start = to_ass_time(item["start"])
        end   = to_ass_time(item["end"])
        text  = item["text"].strip().replace("\n", "\\N")
        lines += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

    return header + lines


@app.post("/render")
async def render_video(
    audio:      UploadFile    = File(...),
    transcript: str           = Form(...),
    chat_id:    Optional[str] = Form(None),
    bg_color:   str           = Form(BG_COLOR_DEFAULT),
    text_color: str           = Form(TEXT_COLOR_DEFAULT),
    font:       str           = Form(FONT_DEFAULT),
    font_size:  str           = Form(FONT_SIZE_DEFAULT),
    bold:       str           = Form(BOLD_DEFAULT),
):
    font_size_int = int(font_size)
    bold_int      = int(bold)

    transcript_data = json.loads(transcript)
    audio_data = await audio.read()

    with tempfile.TemporaryDirectory() as tmp:
        audio_path  = os.path.join(tmp, "audio.mpga")
        ass_path    = os.path.join(tmp, "subs.ass")
        output_path = os.path.join(tmp, "output.mp4")

        with open(audio_path, "wb") as f:
            f.write(audio_data)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(build_ass(transcript_data, text_color, font, font_size_int, bold_int))

        bg = bg_color if bg_color.startswith("#") else f"#{bg_color}"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg}:size=1080x1920:rate=30",
            "-i", audio_path,
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error:\n{result.stderr[-1000:]}")

        with open(output_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode()

    return {"video_base64": video_b64, "chatId": chat_id}


@app.get("/health")
def health():
    return {"status": "ok"}
