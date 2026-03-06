"""Build script that generates Windows version info and runs PyInstaller."""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PYPROJECT = Path("packages/netaudio/pyproject.toml")


def get_version():
    text = PYPROJECT.read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        print("ERROR: Could not find version in", PYPROJECT)
        sys.exit(1)
    return match.group(1)


def version_tuple(version_str):
    parts = version_str.split(".")
    while len(parts) < 4:
        parts.append("0")
    return tuple(int(p) for p in parts[:4])


def generate_version_info(version_str, company):
    tup = version_tuple(version_str)
    return f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={tup},
    prodvers={tup},
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', '{company}'),
        StringStruct('FileDescription', 'Network Audio Controller'),
        StringStruct('FileVersion', '{version_str}'),
        StringStruct('InternalName', 'netaudio'),
        StringStruct('OriginalFilename', 'netaudio.exe'),
        StringStruct('ProductName', 'netaudio'),
        StringStruct('ProductVersion', '{version_str}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""


def main():
    parser = argparse.ArgumentParser(description="Build netaudio with PyInstaller")
    parser.add_argument("--company", default="", help="Company name for version info")
    args = parser.parse_args()

    version_str = get_version()
    print(f"Building netaudio v{version_str}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as f:
        f.write(generate_version_info(version_str, args.company))
        version_file = f.name

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "netaudio",
        "--version-file",
        version_file,
        "packages/netaudio/src/netaudio/__main__.py",
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    Path(version_file).unlink(missing_ok=True)
    print(f"Done! dist/netaudio.exe is v{version_str}")


if __name__ == "__main__":
    main()
