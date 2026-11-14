#!/usr/bin/env python3
"""Make a Scottish voice clip for every Wyndgate hole.

The flyover picture stays in the mp4. The spoken yardage is a separate clip,
voice-wyndgate-<hole>-<tee>.m4a, so the app can play the tee that is selected.
Alba is the en_GB Piper voice trained on
University of Edinburgh speech (CC BY 4.0,
https://datashare.ed.ac.uk/handle/10283/3270). Point PIPER_ALBA_MODEL at
en_GB-alba-medium.onnx.
"""

import json
import os
import subprocess
import wave
from pathlib import Path

from piper import PiperVoice
from piper.config import SynthesisConfig

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "wyndgate_map"
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


def spoken_line(hole, par, tee, yards):
    # "Wind gate" is how The Wyndgate is said.
    yards_words = words(yards)
    yards_words = yards_words[:1].upper() + yards_words[1:]
    return (
        f"Wind gate {words(hole)}. Par {words(par)}. "
        f"{tee} tees. {yards_words} yards."
    )


def encode(wav_path, m4a_path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(wav_path),
            "-af", "adelay=250|250,loudnorm=I=-16:TP=-1.5:LRA=7",
            "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart",
            str(m4a_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def strip_video_audio(video):
    if not video.exists():
        return
    temporary = video.with_suffix(".silent.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-c:v", "copy", "-an", "-movflags", "+faststart", str(temporary)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    temporary.replace(video)


def main():
    voice = PiperVoice.load(MODEL)
    config = SynthesisConfig(length_scale=0.9)
    card = json.loads((MAP / "card.json").read_text())
    tees = card["tees"]
    holes = card["courses"]["wyndgate"]["holes"]
    work = Path("/tmp/wyndgate-voice")
    work.mkdir(exist_ok=True)
    for hole in holes:
        number = hole["hole"]
        for tee in tees:
            yards = hole["yards"][tee["id"]]
            line = spoken_line(number, hole["par"], tee["name"], yards)
            wav_path = work / f"wyndgate-{number}-{tee['id']}.wav"
            with wave.open(str(wav_path), "wb") as wav:
                voice.synthesize_wav(line, wav, syn_config=config)
            m4a = MAP / f"voice-wyndgate-{number}-{tee['id']}.m4a"
            encode(wav_path, m4a)
            print(f"{number} {tee['id']}: {line}")
        strip_video_audio(MAP / f"flyover-wyndgate-{number}.mp4")


if __name__ == "__main__":
    main()
