import sys
from pathlib import Path
from faster_whisper import WhisperModel

def main():
    if len(sys.argv) < 2:
        print('Usage: python transcribe_persian_audio.py "audio_file.aac"')
        return

    audio_path = Path(sys.argv[1])

    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        return

    print("=" * 55)
    print("MABOT - PERSIAN AUDIO TRANSCRIPTION")
    print("=" * 55)

    print("\nLoading Whisper model (medium)...")
    model = WhisperModel(
        "medium",
        device="cpu",
        compute_type="int8",
        cpu_threads=6
    )

    print("\nStarting transcription...")
    segments, info = model.transcribe(
        str(audio_path),
        language="fa",
        clip_timestamps="0,180",
        beam_size=5,
        vad_filter=True,
        initial_prompt="آموزش فارکس، مکدی، هیستوگرام MACD، واگرایی مثبت و منفی، حجم معاملات، تایم فریم هفتگی، خرید، فروش و حد ضرر."
    )

    txt_path = audio_path.with_name(audio_path.stem + "_transcript.txt")
    srt_path = audio_path.with_name(audio_path.stem + "_transcript.srt")

    print(f"\nDetected language: {info.language}")
    print(f"Audio duration: {info.duration / 60:.1f} minutes")

    with open(txt_path, "w", encoding="utf-8") as txt, \
         open(srt_path, "w", encoding="utf-8") as srt:

        for index, segment in enumerate(segments, start=1):
            text = segment.text.strip()

            print(f"[{segment.start/60:.1f} min] {text}")
            txt.write(text + "\n")

            def timestamp(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds - int(seconds)) * 1000)
                return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

            srt.write(f"{index}\n")
            srt.write(
                f"{timestamp(segment.start)} --> "
                f"{timestamp(segment.end)}\n"
            )
            srt.write(text + "\n\n")

    print("\n" + "=" * 55)
    print("TRANSCRIPTION COMPLETED")
    print(f"Text file: {txt_path}")
    print(f"Subtitle file: {srt_path}")
    print("=" * 55)

if __name__ == "__main__":
    main()