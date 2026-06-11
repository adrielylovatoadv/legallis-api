"""Gestão de índices econômicos (BCB/TJSP)."""
import json, os, requests
from datetime import datetime

INDICES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "indices_juridicos.json")
BCB_API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados?formato=json"
TJSP_INPC_URL  = "https://api.tjsp.jus.br/Handlers/Handler/FileFetch.ashx?codigo=189280"
TJSP_14905_URL = "https://api.tjsp.jus.br/Handlers/Handler/FileFetch.ashx?codigo=189281"
MES_MAP_PT = {"JAN":"01","FEV":"02","MAR":"03","ABR":"04","MAI":"05","JUN":"06",
              "JUL":"07","AGO":"08","SET":"09","OUT":"10","NOV":"11","DEZ":"12"}

os.makedirs(os.path.dirname(INDICES_FILE), exist_ok=True)


def _parse_bcb(data: list) -> dict:
    result = {}
    for item in data:
        try:
            parts = item["data"].split("/")
            if len(parts) == 3:
                day, month, year = parts
            else:
                continue
            key = f"{year}-{month}"
            result[key] = float(str(item["valor"]).replace(",", "."))
        except (KeyError, ValueError):
            pass
    return result


def fetch_bcb_series(serie_code: int) -> dict:
    url = BCB_API.format(serie=serie_code)
    resp = requests.get(url, timeout=90)
    resp.raise_for_status()
    return _parse_bcb(resp.json())


def _parse_tjsp_pdf(pdf_bytes: bytes) -> dict:
    import io, re
    try:
        import pdfplumber
    except ImportError:
        return {}
    fatores = {}
    current_anos = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            lines = (page.extract_text() or "").split("\n")
            for line in lines:
                spaced = re.findall(r'\b(\d)\s(\d)\s(\d)\s(\d)\b', line)
                if len(spaced) >= 2:
                    current_anos = ["".join(y) for y in spaced]
                    continue
                m = re.match(r'^\s*(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+(.*)', line)
                if m and current_anos:
                    mes = m.group(1)
                    nums = re.findall(r'[\d]{1,6}[,.][\d]{2,8}', m.group(2))
                    for i, n in enumerate(nums):
                        if i < len(current_anos):
                            try:
                                val = float(n.replace(",", "."))
                                fatores[f"{current_anos[i]}-{MES_MAP_PT[mes]}"] = val
                            except Exception:
                                pass
    return fatores


def _fetch_tjsp_table(url: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tjsp.jus.br/"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return _parse_tjsp_pdf(resp.content)


def update_indices() -> dict:
    inpc  = fetch_bcb_series(188)
    ipcae = fetch_bcb_series(10764)
    selic = fetch_bcb_series(4390)
    try:
        tjsp_inpc = _fetch_tjsp_table(TJSP_INPC_URL)
    except Exception:
        tjsp_inpc = {}
    try:
        tjsp_14905 = _fetch_tjsp_table(TJSP_14905_URL)
    except Exception:
        tjsp_14905 = {}
    indices = {
        "inpc": inpc, "ipcae": ipcae, "selic": selic,
        "tjsp_inpc": tjsp_inpc, "tjsp_14905": tjsp_14905,
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    with open(INDICES_FILE, "w", encoding="utf-8") as f:
        json.dump(indices, f, ensure_ascii=False, indent=2)
    return indices


def load_indices() -> dict:
    if os.path.exists(INDICES_FILE):
        with open(INDICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"inpc": {}, "ipcae": {}, "selic": {}, "tjsp_inpc": {}, "tjsp_14905": {}, "ultima_atualizacao": None}
