import os

sample_banks = [
    ("FoxSE.awave",   0x000000, 0x0E1E30),
    ("FoxMap.awave",   0x0E1E30, 0x0FF9D0),
    ("FoxVoice.awave", 0x1E1800, 0x497480),
    ("FoxBgm.awave",  0x678C80, 0x0C3900),
]

def main():
    with open("bin/us/rev1/audio_table.bin", "rb") as f:
        data = f.read()

    for name, offset, size in sample_banks:
        start = offset
        end = start + size

        chunk = data[start:end]

        os.makedirs("src/assets/audio/waves", exist_ok=True)

        with open(f"src/assets/audio/waves/{name}", "wb") as out:
            out.write(chunk)

        print(f"Extracted {name}")

if __name__ == "__main__":
    main()