import av

source = "mehran 14020817.aac"
output = "mehran_test_3min.wav"

container = av.open(source)
stream = container.streams.audio[0]

resampler = av.AudioResampler(
    format="s16",
    layout="mono",
    rate=16000
)

output_container = av.open(output, mode="w")
output_stream = output_container.add_stream(
    "pcm_s16le",
    rate=16000
)
output_stream.layout = "mono"

for frame in container.decode(stream):
    if frame.time is not None and frame.time >= 180:
        break

    for converted in resampler.resample(frame):
        for packet in output_stream.encode(converted):
            output_container.mux(packet)

for converted in resampler.resample(None):
    for packet in output_stream.encode(converted):
        output_container.mux(packet)

for packet in output_stream.encode(None):
    output_container.mux(packet)

container.close()
output_container.close()

print("3-minute audio created:", output)