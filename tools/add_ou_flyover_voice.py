#!/usr/bin/env python3
"""Add a Scottish voice to each OU hole flyover.

Alba is the en_GB Piper voice trained on University of Edinburgh speech
(CC BY 4.0, https://datashare.ed.ac.uk/handle/10283/3270). The model is not
stored in this repo. Point PIPER_ALBA_MODEL at en_GB-alba-medium.onnx.
"""

import json
import os
import subprocess
import wave
from pathlib import Path

from piper import PiperVoice
from piper.config import SynthesisConfig

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "ou_golf_map"
MODEL = Path(os.environ.get("PIPER_ALBA_MODEL", "/tmp/piper/en_GB-alba-medium.onnx"))
ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(number):
    if number < 20:
        return ONES[number]
    if number < 100:
        tens, rest = divmod(number, 10)
        return TENS[tens - 2] if rest == 0 else f"{TENS[tens - 2]}-{ONES[rest]}"
    hundreds, rest = divmod(number, 100)
    if rest == 0:
        return f"{ONES[hundreds]} hundred"
    return f"{ONES[hundreds]} hundred and {words(rest)}"


def spoken_line(props):
    # "Cat key" and "Sharp" are how the course names are said.
    course = "Cat key" if props["course"] == "katke" else "Sharp"
    return f"{course} {words(props['hole'])}. Par {words(props['par'])}. {words(props['yards'])} yards."


def mux(video, audio):
    temporary = video.with_suffix(".voice.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video), "-i", str(audio),
            "-filter_complex",
            "[1:a]adelay=250|250,apad=pad_dur=30,loudnorm=I=-16:TP=-1.5:LRA=7[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
            "-shortest", "-movflags", "+faststart",
            str(temporary),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    temporary.replace(video)


def main():
    voice = PiperVoice.load(MODEL)
    config = SynthesisConfig(length_scale=0.92)
    holes = json.loads((MAP / "holes.geojson").read_text())["features"]
    work = Path("/tmp/ou-voice")
    work.mkdir(exist_ok=True)
    for feature in holes:
        props = feature["properties"]
        course = "sharf" if props["course"] == "sharf" else "katke"
        line = spoken_line(props)
        wav_path = work / f"{course}-{props['hole']}.wav"
        with wave.open(str(wav_path), "wb") as wav:
            voice.synthesize_wav(line, wav, syn_config=config)
        video = MAP / f"flyover-{course}-{props['hole']}.mp4"
        mux(video, wav_path)
        print(f"{course} {props['hole']}: {line}")


if __name__ == "__main__":
    main()
