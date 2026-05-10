import json
import os
from pathlib import Path
import struct

BANK_HEADER_SIZE = 0x10

def read_u32(data, off):
    return struct.unpack(">I", data[off:off+4])[0]

def read_f32(data, off):
    return struct.unpack(">f", data[off:off+4])[0]

def mssb(x):
    """Find the most significant set bit of x."""
    if x == 0:
        return 0
    
    msb = 0

    while x > 1:
        x >>= 1
        msb += 1
    
    return msb

def write_extended(f, rate):
    shift = mssb(rate)
    expon = 16383 + shift
    hi = int(rate) << (31 - shift)
    lo = 0
    f.write(struct.pack(">HLL", expon, hi, lo))

def parse_instrument(bank_data, inst_ptr, rate_f, samples):
    inst_base = BANK_HEADER_SIZE + inst_ptr

    length = read_u32(bank_data, inst_base)
    offset = read_u32(bank_data, inst_base + 4)

    if length == 0:
        return

    # dedupe by (offset, length)
    key = (offset, length)

    if key not in samples:
        samples[key] = {
            "offset": offset,
            "length": length,
            "rate": min(int(rate_f * 32000), 32000)
        }

def parse_bank(bank_data):
    banks = read_u32(bank_data, 0x00)
    drums = read_u32(bank_data, 0x04)
    bank_offsets = []
    table_off = 0x14

    for i in range(banks):
        off = read_u32(bank_data, table_off + i * 4)

        if off != 0:
            bank_offsets.append(off)
    
    drum_offsets = []
    drum_off  = read_u32(bank_data, 0x10) + BANK_HEADER_SIZE
    
    for i in range(drums):
        off = read_u32(bank_data, drum_off + i * 4)

        if off != 0:
            drum_offsets.append(off)

    samples = {}

    for bank_off in bank_offsets:
        base = BANK_HEADER_SIZE + bank_off
        c3_inst_ptr = read_u32(bank_data, base + 0x8)
        rate_f   = read_f32(bank_data, base + 0xC) / 2

        if c3_inst_ptr != 0:
            parse_instrument(bank_data, c3_inst_ptr, rate_f, samples)

        c4_inst_ptr = read_u32(bank_data, base + 0x10)
        rate_f   = read_f32(bank_data, base + 0x14)

        if c4_inst_ptr != 0:
            parse_instrument(bank_data, c4_inst_ptr, rate_f, samples)

        c5_inst_ptr = read_u32(bank_data, base + 0x18)
        rate_f   = read_f32(bank_data, base + 0x1C) * 2

        if c5_inst_ptr != 0:
            parse_instrument(bank_data, c5_inst_ptr, rate_f, samples)
    
    drum_rates = {}
    
    for drum_off in drum_offsets:
        base = BANK_HEADER_SIZE + drum_off
        sample = read_u32(bank_data, base + 4)
        rate_f = read_f32(bank_data, base + 8)

        if sample != 0:
            if sample in drum_rates:
                drum_rates[sample] = min(max(drum_rates[sample], rate_f), 1)
            else:
                drum_rates[sample] = min(rate_f, 1)
    
    for drum, rate in drum_rates.items():
        parse_instrument(bank_data, drum, rate, samples)
        
    return list(samples.values())


def extract_samples(bank_path, awave_path, out_dir, name_list, sample_set):
    with open(bank_path, "rb") as f:
        bank_data = f.read()

    with open(awave_path, "rb") as f:
        awave_data = f.read()

    samples = parse_bank(bank_data)

    for i, s in enumerate(samples):
        start = s["offset"]
        end   = start + s["length"]

        chunk = awave_data[start:end]

        with open(f"{out_dir}/{name_list[i]}", "wb") as f:
            f.write(b"FORM")
            f.write(struct.pack(">I", len(chunk) + 0xB8))
            f.write(b"AIFC")
            f.write(b"COMM")
            f.write(struct.pack(">I", 34))
            f.write(struct.pack(">H", 1))  # channels
            num_frames = s["length"] * 16 // 9  # rough estimate
            f.write(struct.pack(">I", num_frames))
            f.write(struct.pack(">H", 16))  # sample size
            write_extended(f, s["rate"])
            f.write(b"VAPC\vVADPCM ~4-1")  # Nintendo ADPCM
            f.write(b"INST")
            f.write(struct.pack(">I", 20)) # size of INST chunk
            f.write(struct.pack(">B", 0x3C))  # unity note (60 = middle C)
            f.write(struct.pack(">B", 0))     # detune
            f.write(struct.pack(">B", 0))     # low note
            f.write(struct.pack(">B", 127))   # high note
            f.write(struct.pack(">B", 0))     # low velocity
            f.write(struct.pack(">B", 127))   # high velocity
            f.write(struct.pack(">H", 0))     # gain
            f.write(struct.pack(">HHH", 0, 0, 0))     # sustainLoop: mode, start, end
            f.write(struct.pack(">HHH", 0, 0, 0))     # releaseLoop: mode, start, end
            f.write(b"APPL")
            f.write(struct.pack(">I", 86))
            f.write(b"stoc\vVADPCMCODES")
            f.write(struct.pack(">HHH", 1, 2, 2))
            f.write(struct.pack(">IIIIIIIIIIIIIIII",
                                0xFC41FE50, 0x00FF013D, 0x0017FF76, 0xFFB70020,
                                0x039AFDE0, 0xFD5BFFCE, 0x0127009C, 0xFFBCFF98,
                                0xFB39FA38, 0xFBDBFE6F, 0x009401A3, 0x01A20100,
                                0x09AF06F1, 0x029FFF07, 0xFD42FD43, 0xFE53FF9B))
            f.write(b"SSND")
            f.write(struct.pack(">I", len(chunk) + 8))
            f.write(struct.pack(">II", 0, 0))  # offset, block size
            f.write(chunk)
        
        sample_set[s["offset"]] = [ name_list[i], s["length"], bank_path ]

    print(f"Extracted {len(samples)} samples")

def main():
    with open("tools/instruments.json", "r") as f:
        config = json.load(f)

    samples = {}
    
    for awave_path, awave in config.items():
        for dir in awave["dirs"]:
            os.makedirs(f"src/assets/audio/{dir}", exist_ok=True)

        for bank_path, sample_list in awave["banks"].items():
            extract_samples(
                bank_path = f"src/assets/audio/{bank_path}",
                awave_path = f"src/assets/audio/{awave_path}",
                out_dir = "src/assets/audio",
                name_list = sample_list,
                sample_set = samples
            )

    with open("src/assets/audio/samples.json", "w") as f:
        json.dump(samples, f)

if __name__ == "__main__":
    main()