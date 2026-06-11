"""Router Financeiro Escritório."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json, uuid
from pathlib import Path

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "financeiro_data.json"
DATA_FILE.parent.mkdir(exist_ok=True)

MESES = [
    "Out/2025","Nov/2025","Dez/2025",
    "Jan/2026","Fev/2026","Mar/2026","Abr/2026","Mai/2026","Jun/2026",
    "Jul/2026","Ago/2026","Set/2026","Out/2026","Nov/2026","Dez/2026",
    "Jan/2027","Fev/2027","Mar/2027","Abr/2027","Mai/2027","Jun/2027",
    "Jul/2027","Ago/2027","Set/2027","Out/2027","Nov/2027","Dez/2027",
]

COL_TO_MES = {
    "Out":"Out/2025","Nov":"Nov/2025","Dez":"Dez/2025",
    "Jan":"Jan/2026","Fev":"Fev/2026","Mar":"Mar/2026","Abr":"Abr/2026",
    "Mai":"Mai/2026","Jun":"Jun/2026","Jul":"Jul/2026","Ago":"Ago/2026",
    "Set":"Set/2026","Out2":"Out/2026","Nov2":"Nov/2026","Dez2":"Dez/2026",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _load() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    origem = Path("/Users/adrielylovato/financeiro_escritorio/financeiro_data.json")
    if origem.exists():
        with open(origem, encoding="utf-8") as f:
            d = json.load(f)
        _ensure_ids(d)
        _save(d)
        return d
    return {"acordos": [], "execucoes": [], "honorarios_iniciais": [],
            "fixas": {}, "fixas_quem": {}, "fixas_status": {}, "variaveis": []}


def _ensure_ids(d: dict):
    for lista in ("acordos", "execucoes", "honorarios_iniciais", "variaveis"):
        for item in d.get(lista, []):
            if "id" not in item:
                item["id"] = _new_id()


def _save(data: dict):
    _ensure_ids(data)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _calc_acordo(valor: float) -> float:
    return round(valor * 0.10 + (valor * 0.90) * 0.35, 2)


def _calc_execucao(percebido: float, sucumbencia: float) -> float:
    return round(percebido * 0.35 + sucumbencia, 2)


# ── modelos ───────────────────────────────────────────────────────────────────

class AcordoIn(BaseModel):
    mes: str
    data_pagamento: Optional[str] = ""
    cliente: str
    reu: Optional[str] = ""
    objeto: Optional[str] = ""
    processo: Optional[str] = ""
    valor_acordo: float = 0.0
    status: str = "pendente"   # pago | pendente | repasse


class ExecucaoIn(BaseModel):
    mes: str
    data_pagamento: Optional[str] = ""
    cliente: str
    reu: Optional[str] = ""
    processo: Optional[str] = ""
    valor_percebido: float = 0.0
    sucumbencia: float = 0.0
    status: str = "pendente"


class HonorarioInicialIn(BaseModel):
    cliente: str
    processo: Optional[str] = ""
    valor: float = 0.0
    data_pagamento: Optional[str] = ""
    observacao: Optional[str] = ""
    status: str = "pendente"


class FixaValoresIn(BaseModel):
    categoria: str
    quem: str = "dividido"
    valores: Dict[str, float] = {}   # col → valor


class VariavelIn(BaseModel):
    descricao: str
    valor: float = 0.0
    parcelas: Optional[str] = "1x"
    quem: str = "dividido"
    onde: Optional[str] = ""
    status: str = "pendente"
    data_compra: Optional[str] = ""
    meses: Dict[str, float] = {}     # col → valor


class StatusUpdate(BaseModel):
    status: str


# ── acordos ───────────────────────────────────────────────────────────────────

@router.get("/acordos")
def listar_acordos():
    d = _load()
    result = []
    for a in d.get("acordos", []):
        item = dict(a)
        item["honorarios"] = _calc_acordo(float(a.get("valor_acordo", 0)))
        result.append(item)
    return result


@router.post("/acordos")
def criar_acordo(ac: AcordoIn):
    d = _load()
    novo = {"id": _new_id(), **ac.model_dump(),
            "honorarios": _calc_acordo(ac.valor_acordo)}
    d["acordos"].append(novo)
    _save(d)
    return novo


@router.put("/acordos/{aid}")
def atualizar_acordo(aid: str, ac: AcordoIn):
    d = _load()
    for i, a in enumerate(d["acordos"]):
        if a.get("id") == aid:
            d["acordos"][i] = {**a, **ac.model_dump(), "id": aid,
                               "honorarios": _calc_acordo(ac.valor_acordo)}
            _save(d)
            return d["acordos"][i]
    raise HTTPException(404, "Acordo não encontrado")


@router.patch("/acordos/{aid}/status")
def status_acordo(aid: str, body: StatusUpdate):
    d = _load()
    for a in d["acordos"]:
        if a.get("id") == aid:
            a["status"] = body.status
            _save(d)
            return a
    raise HTTPException(404)


@router.delete("/acordos/{aid}")
def excluir_acordo(aid: str):
    d = _load()
    d["acordos"] = [a for a in d["acordos"] if a.get("id") != aid]
    _save(d)
    return {"ok": True}


# ── execuções ─────────────────────────────────────────────────────────────────

@router.get("/execucoes")
def listar_execucoes():
    d = _load()
    result = []
    for e in d.get("execucoes", []):
        item = dict(e)
        item["honorarios"] = _calc_execucao(float(e.get("valor_percebido", 0)), float(e.get("sucumbencia", 0)))
        result.append(item)
    return result


@router.post("/execucoes")
def criar_execucao(ex: ExecucaoIn):
    d = _load()
    novo = {"id": _new_id(), **ex.model_dump(),
            "honorarios": _calc_execucao(ex.valor_percebido, ex.sucumbencia)}
    d["execucoes"].append(novo)
    _save(d)
    return novo


@router.put("/execucoes/{eid}")
def atualizar_execucao(eid: str, ex: ExecucaoIn):
    d = _load()
    for i, e in enumerate(d["execucoes"]):
        if e.get("id") == eid:
            d["execucoes"][i] = {**e, **ex.model_dump(), "id": eid,
                                 "honorarios": _calc_execucao(ex.valor_percebido, ex.sucumbencia)}
            _save(d)
            return d["execucoes"][i]
    raise HTTPException(404)


@router.patch("/execucoes/{eid}/status")
def status_execucao(eid: str, body: StatusUpdate):
    d = _load()
    for e in d["execucoes"]:
        if e.get("id") == eid:
            e["status"] = body.status
            _save(d)
            return e
    raise HTTPException(404)


@router.delete("/execucoes/{eid}")
def excluir_execucao(eid: str):
    d = _load()
    d["execucoes"] = [e for e in d["execucoes"] if e.get("id") != eid]
    _save(d)
    return {"ok": True}


# ── honorários iniciais ───────────────────────────────────────────────────────

@router.get("/honorarios-iniciais")
def listar_hon_iniciais():
    return _load().get("honorarios_iniciais", [])


@router.post("/honorarios-iniciais")
def criar_hon_inicial(hi: HonorarioInicialIn):
    d = _load()
    novo = {"id": _new_id(), **hi.model_dump()}
    d["honorarios_iniciais"].append(novo)
    _save(d)
    return novo


@router.put("/honorarios-iniciais/{hid}")
def atualizar_hon_inicial(hid: str, hi: HonorarioInicialIn):
    d = _load()
    for i, h in enumerate(d["honorarios_iniciais"]):
        if h.get("id") == hid:
            d["honorarios_iniciais"][i] = {**h, **hi.model_dump(), "id": hid}
            _save(d)
            return d["honorarios_iniciais"][i]
    raise HTTPException(404)


@router.patch("/honorarios-iniciais/{hid}/status")
def status_hon_inicial(hid: str, body: StatusUpdate):
    d = _load()
    for h in d["honorarios_iniciais"]:
        if h.get("id") == hid:
            h["status"] = body.status
            _save(d)
            return h
    raise HTTPException(404)


@router.delete("/honorarios-iniciais/{hid}")
def excluir_hon_inicial(hid: str):
    d = _load()
    d["honorarios_iniciais"] = [h for h in d["honorarios_iniciais"] if h.get("id") != hid]
    _save(d)
    return {"ok": True}


# ── despesas fixas ────────────────────────────────────────────────────────────

@router.get("/fixas")
def listar_fixas():
    d = _load()
    result = []
    for cat, valores in d.get("fixas", {}).items():
        result.append({
            "categoria": cat,
            "quem": d.get("fixas_quem", {}).get(cat, "dividido"),
            "valores": valores,
            "status": d.get("fixas_status", {}).get(cat, {}),
            "total": sum(float(v) for v in valores.values()),
        })
    return result


@router.post("/fixas")
def criar_fixa(fixa: FixaValoresIn):
    d = _load()
    if fixa.categoria in d.get("fixas", {}):
        raise HTTPException(400, "Categoria já existe")
    d.setdefault("fixas", {})[fixa.categoria] = fixa.valores
    d.setdefault("fixas_quem", {})[fixa.categoria] = fixa.quem
    d.setdefault("fixas_status", {})[fixa.categoria] = {}
    _save(d)
    return {"ok": True}


@router.put("/fixas/{categoria}")
def atualizar_fixa(categoria: str, fixa: FixaValoresIn):
    d = _load()
    d.setdefault("fixas", {})[categoria] = fixa.valores
    d.setdefault("fixas_quem", {})[categoria] = fixa.quem
    _save(d)
    return {"ok": True}


# ── despesas variáveis ────────────────────────────────────────────────────────

@router.get("/variaveis")
def listar_variaveis():
    return _load().get("variaveis", [])


@router.post("/variaveis")
def criar_variavel(v: VariavelIn):
    d = _load()
    novo = {"id": _new_id(), **v.model_dump()}
    d.setdefault("variaveis", []).append(novo)
    _save(d)
    return novo


@router.put("/variaveis/{vid}")
def atualizar_variavel(vid: str, v: VariavelIn):
    d = _load()
    for i, item in enumerate(d.get("variaveis", [])):
        if item.get("id") == vid:
            d["variaveis"][i] = {**item, **v.model_dump(), "id": vid}
            _save(d)
            return d["variaveis"][i]
    raise HTTPException(404)


@router.patch("/variaveis/{vid}/status")
def status_variavel(vid: str, body: StatusUpdate):
    d = _load()
    for v in d.get("variaveis", []):
        if v.get("id") == vid:
            v["status"] = body.status
            _save(d)
            return v
    raise HTTPException(404)


@router.delete("/variaveis/{vid}")
def excluir_variavel(vid: str):
    d = _load()
    d["variaveis"] = [v for v in d.get("variaveis", []) if v.get("id") != vid]
    _save(d)
    return {"ok": True}


# ── dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard():
    d = _load()

    # Receitas
    hon_acordos_recebidos = sum(
        _calc_acordo(float(a.get("valor_acordo", 0)))
        for a in d.get("acordos", []) if a.get("status") in ("pago", "repasse")
    )
    hon_exec_recebidos = sum(
        _calc_execucao(float(e.get("valor_percebido", 0)), float(e.get("sucumbencia", 0)))
        for e in d.get("execucoes", []) if e.get("status") in ("pago", "repasse")
    )
    hon_iniciais_recebidos = sum(
        float(h.get("valor", 0)) for h in d.get("honorarios_iniciais", [])
        if h.get("status") == "pago"
    )
    total_recebido = hon_acordos_recebidos + hon_exec_recebidos + hon_iniciais_recebidos

    hon_acordos_pend = sum(
        _calc_acordo(float(a.get("valor_acordo", 0)))
        for a in d.get("acordos", []) if a.get("status") == "pendente"
    )
    hon_exec_pend = sum(
        _calc_execucao(float(e.get("valor_percebido", 0)), float(e.get("sucumbencia", 0)))
        for e in d.get("execucoes", []) if e.get("status") == "pendente"
    )
    hon_iniciais_pend = sum(
        float(h.get("valor", 0)) for h in d.get("honorarios_iniciais", [])
        if h.get("status") == "pendente"
    )
    total_pendente = hon_acordos_pend + hon_exec_pend + hon_iniciais_pend

    # Despesas
    total_fixas = sum(
        sum(float(v) for v in vals.values())
        for vals in d.get("fixas", {}).values()
    )
    total_variaveis = sum(
        sum(float(v) for v in item.get("meses", {}).values())
        for item in d.get("variaveis", [])
    )
    saldo = total_recebido - total_fixas - total_variaveis

    # Por mês
    honor_mes: dict = {}
    for a in d.get("acordos", []):
        m = a.get("mes", "")
        honor_mes[m] = honor_mes.get(m, 0) + _calc_acordo(float(a.get("valor_acordo", 0)))
    for e in d.get("execucoes", []):
        m = e.get("mes", "")
        honor_mes[m] = honor_mes.get(m, 0) + _calc_execucao(float(e.get("valor_percebido", 0)), float(e.get("sucumbencia", 0)))

    fixas_mes: dict = {}
    for vals in d.get("fixas", {}).values():
        for col, val in vals.items():
            m = COL_TO_MES.get(col, "")
            fixas_mes[m] = fixas_mes.get(m, 0) + float(val or 0)

    var_mes: dict = {}
    for item in d.get("variaveis", []):
        for col, val in item.get("meses", {}).items():
            m = COL_TO_MES.get(col, "")
            var_mes[m] = var_mes.get(m, 0) + float(val or 0)

    meses_com_dados = [m for m in MESES if honor_mes.get(m, 0) + fixas_mes.get(m, 0) + var_mes.get(m, 0) > 0]
    resumo_mes = [
        {"mes": m, "honorarios": round(honor_mes.get(m, 0), 2),
         "fixas": round(fixas_mes.get(m, 0), 2),
         "variaveis": round(var_mes.get(m, 0), 2),
         "saldo": round(honor_mes.get(m, 0) - fixas_mes.get(m, 0) - var_mes.get(m, 0), 2)}
        for m in meses_com_dados
    ]

    # Pendentes
    pendentes = []
    for a in d.get("acordos", []):
        if a.get("status") == "pendente":
            pendentes.append({"tipo": "acordo", "cliente": a.get("cliente", ""),
                               "mes": a.get("mes", ""), "valor": _calc_acordo(float(a.get("valor_acordo", 0))),
                               "processo": a.get("processo", "")})
    for e in d.get("execucoes", []):
        if e.get("status") == "pendente":
            pendentes.append({"tipo": "execucao", "cliente": e.get("cliente", ""),
                               "mes": e.get("mes", ""),
                               "valor": _calc_execucao(float(e.get("valor_percebido", 0)), float(e.get("sucumbencia", 0))),
                               "processo": e.get("processo", "")})
    for h in d.get("honorarios_iniciais", []):
        if h.get("status") == "pendente":
            pendentes.append({"tipo": "honorario_inicial", "cliente": h.get("cliente", ""),
                               "mes": "", "valor": float(h.get("valor", 0)),
                               "observacao": h.get("observacao", "")})

    return {
        "total_recebido": round(total_recebido, 2),
        "total_pendente": round(total_pendente, 2),
        "total_fixas": round(total_fixas, 2),
        "total_variaveis": round(total_variaveis, 2),
        "saldo": round(saldo, 2),
        "resumo_mes": resumo_mes,
        "pendentes": pendentes,
    }
