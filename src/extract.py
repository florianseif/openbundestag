"""Download session XML files from Bundestag Open Data endpoints.

Uses Playwright (via subprocess) to handle the JS-based bot-protection
(Enodia challenge) that blocks plain HTTP clients.
"""

import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# MdB master data (Stammdaten) — one ZIP holding MDB_STAMMDATEN.XML with every
# Bundestag member since 1949, their official 8-digit ID, name history and the
# faction per electoral term.  Unlike the session archives this blob serves a
# plain HTTP client fine (no bot challenge), so a direct download is enough.
STAMMDATEN_URL = "https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip"
STAMMDATEN_XML = "MDB_STAMMDATEN.XML"

# Structured XML per session — modern terms
FILTERLIST_URLS: dict[int, str] = {
    19: "https://www.bundestag.de/ajax/filterlist/de/services/opendata/543410-543410?offset={}",
    20: "https://www.bundestag.de/ajax/filterlist/de/services/opendata/866354-866354?offset={}",
    21: "https://www.bundestag.de/ajax/filterlist/de/services/opendata/1058442-1058442?offset={}",
}

# Legacy ZIP archives — terms 1–18
LEGACY_ZIP_URLS: dict[int, str] = {
    18: "https://www.bundestag.de/resource/blob/490392/90738376bb195628b95d117ab5392cfe/pp18-data.zip",
    17: "https://www.bundestag.de/resource/blob/490378/033276846771aac12dd7109724a1134b/pp17-data.zip",
    16: "https://www.bundestag.de/resource/blob/490386/80886372e6bbe903dd4d7eb03fe424b3/pp16-data.zip",
    15: "https://www.bundestag.de/resource/blob/490394/08411d0257e9e07daef24001a958db53/pp15-data.zip",
    14: "https://www.bundestag.de/resource/blob/490380/c4ca5488b447668f802039f1f769b278/pp14-data.zip",
    13: "https://www.bundestag.de/resource/blob/490388/84914a1feff6f2f4988ce352a5500845/pp13-data.zip",
    12: "https://www.bundestag.de/resource/blob/490376/8775517464dccd8660eb96446d18dd26/pp12-data.zip",
    11: "https://www.bundestag.de/resource/blob/490384/ad57841a599aba6faa794174e53a8797/pp11-data.zip",
    10: "https://www.bundestag.de/resource/blob/490374/07ce06f666b624d37b47d2fe6e205ab4/pp10-data.zip",
    9:  "https://www.bundestag.de/resource/blob/490382/effcc03f3b3e157f9d8050b4a9d9d089/pp09-data.zip",
    8:  "https://www.bundestag.de/resource/blob/490390/dfcac024ce8e548774e16f03c36293e2/pp08-data.zip",
    7:  "https://www.bundestag.de/resource/blob/488222/b10bae395e887aac9ac08afbd1da62fc/pp07-data.zip",
    6:  "https://www.bundestag.de/resource/blob/488220/b2b4d0d49600ef852d15e4052fabce1e/pp06-data.zip",
    5:  "https://www.bundestag.de/resource/blob/488218/bfba1a02d1090efc873f9a60f318a162/pp05-data.zip",
    4:  "https://www.bundestag.de/resource/blob/488216/3b20f8dd5efad2cafa3fb0b6df24cbb9/pp04-data.zip",
    3:  "https://www.bundestag.de/resource/blob/487970/1c737594587745b399e84bc30f049d69/pp03-data.zip",
    2:  "https://www.bundestag.de/resource/blob/487968/5792895a5cf4ab51ed94c77157297031/pp02-data.zip",
    1:  "https://www.bundestag.de/resource/blob/487966/4078f01fb3198dc3cee8945d6db3b231/pp01-data.zip",
}

ALL_TERMS = sorted(list(FILTERLIST_URLS) + list(LEGACY_ZIP_URLS))

_WORKER = Path(__file__).with_name("_pw_download.py")


def download_term(wahlperiode: int, data_dir: str | Path) -> Path:
    """Download all session XMLs for *wahlperiode* into *data_dir/term_XX/*.

    Delegates to a Playwright subprocess to pass the Bundestag bot-protection
    challenge.  Already-downloaded files are skipped so the command is re-entrant.
    """
    data_dir = Path(data_dir)
    term_dir = data_dir / f"term_{wahlperiode:02d}"
    term_dir.mkdir(parents=True, exist_ok=True)

    if wahlperiode in FILTERLIST_URLS:
        _run_worker("modern", wahlperiode, term_dir, FILTERLIST_URLS[wahlperiode])
    elif wahlperiode in LEGACY_ZIP_URLS:
        _run_worker("legacy", wahlperiode, term_dir, LEGACY_ZIP_URLS[wahlperiode])
    else:
        raise ValueError(
            f"Wahlperiode {wahlperiode} is not configured. "
            f"Supported terms: {ALL_TERMS}"
        )
    return term_dir


def download_stammdaten(data_dir: str | Path) -> Path:
    """Download and unpack the MdB-Stammdaten XML into *data_dir/stammdaten/*.

    Returns the path to the extracted ``MDB_STAMMDATEN.XML``.  Re-entrant: if the
    XML already exists it is reused (pass ``force=True`` semantics by deleting it
    first).  This blob is not behind the bot-protection, so a plain urllib fetch
    works without the Playwright worker the session archives need.
    """
    data_dir = Path(data_dir)
    out_dir = data_dir / "stammdaten"
    out_dir.mkdir(parents=True, exist_ok=True)
    xml_path = out_dir / STAMMDATEN_XML

    if xml_path.exists():
        print(f"[extract] Stammdaten already present → {xml_path}", flush=True)
        return xml_path

    zip_path = out_dir / "MdB-Stammdaten.zip"
    print(f"[extract] Downloading Stammdaten → {STAMMDATEN_URL}", flush=True)
    req = urllib.request.Request(STAMMDATEN_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as fh:
        fh.write(resp.read())

    with zipfile.ZipFile(zip_path) as zf:
        zf.extract(STAMMDATEN_XML, out_dir)
    zip_path.unlink(missing_ok=True)

    print(f"[extract] Stammdaten extracted → {xml_path}", flush=True)
    return xml_path


def _run_worker(mode: str, wahlperiode: int, term_dir: Path, url: str) -> None:
    cmd = [sys.executable, str(_WORKER), mode, str(wahlperiode), str(term_dir), url]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"Download worker failed for term {wahlperiode} (exit {result.returncode})"
        )
