"""Generate the synthetic canary CV PDF (no real personal data).

Pure standard library; the output is deterministic for the fixed line list.
Usage: python tools/make_synthetic_canary_pdf.py <out.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

LINES = [
    "SYNTHETIC CANARY CV",
    "CANARY APPLICANT",
    "Profile",
    "Cloud engineer with five years of experience.",
    "Experience",
    "Built an AWS platform with Python and Terraform.",
    "Education",
    "MSc Computer Science",
    "Skills",
    "Python, AWS, Terraform, Docker, Linux, SQL",
    "Languages",
    "German, English",
    "Location",
    "Berlin",
]


def escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def build() -> bytes:
    commands = ["BT", "/F1 12 Tf", "60 790 Td"]
    for index, line in enumerate(LINES):
        if index:
            commands.append("0 -22 Td")
        commands.append(f"({escape(line)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
         b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode("ascii")
    return bytes(out)


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    target = Path(argv[0] if argv else "synthetic-canary-cv.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build())
    print(f"{target} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
