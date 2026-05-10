from datetime import date
import json
import os
import struct

def int_to_bcd(value):
    """Convert an integer to a BCD byte string."""
    ret = 0
    digits = 0

    while value:
        value, ls4b = divmod(value, 10)
        value, ms4b = divmod(value, 10)
        ret += ((ms4b << 4) + ls4b) << (digits * 4)
        digits += 2
    
    return ret
def bcd_timestamp():
    today = date.today()

    return int_to_bcd(today.year * 10000 + today.month * 100 + today.day)

def main():
    with open("tools/banks.us.r1.json") as f:
        banks = json.load(f)

    with open("bin/us/rev1/audio_bank.bin", "rb") as f:
        data = f.read()

    for name, info in banks.items():
        start = int(info["start"], 16)
        size = int(info["size"], 16)

        instruments = int(info["instruments"])
        drums = int(info["drums"])

        bank_data = data[start:start + size]

        header = struct.pack(
            ">IIII",  # big-endian
            instruments,
            drums,
            0,                 # unknown
            int(bcd_timestamp())
        )

        os.makedirs("src/assets/audio/banks", exist_ok=True)

        with open(f"src/assets/audio/banks/{name}", "wb") as out:
            out.write(header)
            out.write(bank_data)

        print(f"Extracted {name}")

if __name__ == "__main__":
    main()