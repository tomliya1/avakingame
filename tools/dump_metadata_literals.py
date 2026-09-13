#!/usr/bin/env python3
"""
Dump the string-literal table from a Unity IL2CPP `global-metadata.dat`.

Why this exists
---------------
Running `strings` on global-metadata.dat does NOT give you usable literals.
The literal data blob is *length-prefixed*, not null-terminated, so every
literal runs into the next one and you get a handful of enormous lines.

The metadata header points at a real table of {length, dataIndex} pairs.
Walking that table recovers each literal exactly.

Validated against Avakin Life 2.23.0: recovers 139/139 of the REST endpoints
that were independently extracted from decompiled C# source. Zero misses.

Usage
-----
    python3 dump_metadata_literals.py <global-metadata.dat> [-o out.txt]

    # every REST endpoint in the client
    python3 dump_metadata_literals.py global-metadata.dat \
        | grep -aE '^[a-z][a-zA-Z0-9_-]*/[0-9]+/[a-zA-Z0-9_/{}.?=&-]+$' | sort -u

    # diff two versions
    python3 dump_metadata_literals.py old.dat -o old.txt
    python3 dump_metadata_literals.py new.dat -o new.txt
    comm -13 <(sort -u old.txt) <(sort -u new.txt)

Limitation
----------
Only *statically compiled* strings appear here. A path assembled at runtime
(e.g. ZString.Concat("ws/1/", svc, "/get")) never exists as a literal and is
invisible to this tool. Format templates such as "usermail/{0}/usermail/2/{1}"
ARE literals and are captured. To detect runtime composition, check for bare
"<word>/<digit>" service-prefix fragments in the output; for full fidelity use
Il2CppDumper + a decompiler, or hook the request builder at runtime.

Header layout used (metadata v24-v31, little-endian):
    +0  uint32  sanity = 0xFAB11BAF
    +4  int32   version
    +8  uint32  stringLiteralOffset      (table of 8-byte entries)
    +12 int32   stringLiteralSize        (bytes)
    +16 uint32  stringLiteralDataOffset  (the blob)
    +20 int32   stringLiteralDataSize    (bytes)
"""

import argparse
import struct
import sys

SANITY = 0xFAB11BAF
ENTRY_SIZE = 8  # uint32 length + int32 dataIndex


def dump_literals(path):
    with open(path, "rb") as fh:
        data = fh.read()

    if len(data) < 24:
        raise ValueError("file too small to be global-metadata.dat")

    sanity, version = struct.unpack_from("<Ii", data, 0)
    if sanity != SANITY:
        raise ValueError(
            f"bad sanity 0x{sanity:08X} (expected 0x{SANITY:08X}) — not a global-metadata.dat?"
        )
    if not 24 <= version <= 31:
        print(
            f"warning: metadata version {version} is outside the tested range 24-31; "
            "header offsets may differ",
            file=sys.stderr,
        )

    lit_off, lit_size = struct.unpack_from("<Ii", data, 8)
    dat_off, dat_size = struct.unpack_from("<Ii", data, 16)

    count = lit_size // ENTRY_SIZE
    literals, skipped = [], 0

    for i in range(count):
        length, index = struct.unpack_from("<Ii", data, lit_off + i * ENTRY_SIZE)
        if length < 0 or index < 0 or index + length > dat_size:
            skipped += 1
            continue
        raw = data[dat_off + index : dat_off + index + length]
        literals.append(raw.decode("utf-8", "replace"))

    return version, literals, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("metadata", help="path to global-metadata.dat")
    ap.add_argument("-o", "--out", help="write here instead of stdout")
    ap.add_argument("--raw", action="store_true",
                    help="keep duplicates and original order (default: unique + sorted)")
    args = ap.parse_args()

    try:
        version, literals, skipped = dump_literals(args.metadata)
    except (OSError, ValueError) as exc:
        sys.exit(f"error: {exc}")

    out = literals if args.raw else sorted(set(literals))
    # Escape newlines so one literal always occupies exactly one output line.
    lines = (s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r") for s in out)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.writelines(line + "\n" for line in lines)
        dest = args.out
    else:
        for line in lines:
            print(line)
        dest = "stdout"

    print(
        f"metadata v{version}: {len(literals)} literals "
        f"({len(set(literals))} unique) -> {dest}"
        + (f"; {skipped} malformed entries skipped" if skipped else ""),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
