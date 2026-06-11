"""Router de Controle Processual."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json, uuid
from pathlib import Path

router = APIRouter()

DATA_FILE = Path(__file__).parent.parent / "data" / "controle_data.json"
DATA_FILE.parent.mkdir(exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    # tenta copiar do app Streamlit original
    origem = Path("/Users/adrielylovato/controle_processual/controle_data.json")
    if origem.exists():
        with open(origem, encoding="utf-8") as f:
            d = json.load(f)
        _save(d)
        return d
    return {"processos": [], "clientes": [], "iniciais": []}


def _save(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


def _now() -> str:
    return datetime.now().isoformat()


# ── modelos ───────────────────────────────────────────────────────────────────

class ProcessoIn(BaseModel):
    autor: str
    reu: Optional[str] = ""
    objeto: Optional[str] = ""
    numero_processo: Optional[str] = ""
    data: Optional[str] = ""          # YYYY-MM-DD
    hora: Optional[str] = ""
    andamento: Optional[str] = ""
    responsavel: Optional[str] = ""
    observacoes: Optional[str] = ""
    atencao: Optional[bool] = False
    finalizado: Optional[bool] = False


class ClienteIn(BaseModel):
    nome: str
    telefone: Optional[str] = ""
    cpf: Optional[str] = ""
    email: Optional[str] = ""
    endereco: Optional[str] = ""
    tipo_aposentadoria: Optional[str] = ""
    informacoes: Optional[str] = ""
    senha_gov: Optional[str] = ""
    senha_serasa: Optional[str] = ""


class InicialIn(BaseModel):
    cliente: str
    reu: Optional[str] = ""
    objeto: Optional[str] = ""
    andamento: Optional[str] = ""
    responsavel: Optional[str] = ""
    observacoes: Optional[str] = ""


# ── processos ─────────────────────────────────────────────────────────────────

@router.get("/processos")
def listar_processos(busca: str = "", andamento: str = "", finalizado: Optional[bool] = None):
    data = _load()
    lista = data.get("processos", [])
    if busca:
        b = busca.lower()
        lista = [p for p in lista if
                 b in (p.get("autor") or "").lower() or
                 b in (p.get("reu") or "").lower() or
                 b in (p.get("numero_processo") or "").lower() or
                 b in (p.get("objeto") or "").lower()]
    if andamento:
        lista = [p for p in lista if andamento.upper() in (p.get("andamento") or "").upper()]
    if finalizado is not None:
        lista = [p for p in lista if bool(p.get("finalizado")) == finalizado]
    return lista


@router.post("/processos")
def criar_processo(proc: ProcessoIn):
    data = _load()
    novo = {"id": _new_id(), "criado_em": _now(), **proc.model_dump()}
    data["processos"].append(novo)
    _save(data)
    return novo


@router.put("/processos/{pid}")
def atualizar_processo(pid: str, proc: ProcessoIn):
    data = _load()
    for i, p in enumerate(data["processos"]):
        if p["id"] == pid:
            data["processos"][i] = {**p, **proc.model_dump(), "id": pid}
            _save(data)
            return data["processos"][i]
    raise HTTPException(404, "Processo não encontrado")


@router.delete("/processos/{pid}")
def excluir_processo(pid: str):
    data = _load()
    antes = len(data["processos"])
    data["processos"] = [p for p in data["processos"] if p["id"] != pid]
    if len(data["processos"]) == antes:
        raise HTTPException(404, "Processo não encontrado")
    _save(data)
    return {"ok": True}


@router.post("/processos/{pid}/ok")
def marcar_ok(pid: str):
    """Zera data/hora/andamento após cumprimento de prazo."""
    data = _load()
    for p in data["processos"]:
        if p["id"] == pid:
            p["data"] = ""
            p["hora"] = ""
            p["andamento"] = "AGUARDANDO DESPACHO"
            p["responsavel"] = ""
            _save(data)
            return p
    raise HTTPException(404, "Processo não encontrado")


# ── clientes ──────────────────────────────────────────────────────────────────

@router.get("/clientes")
def listar_clientes(busca: str = ""):
    data = _load()
    lista = data.get("clientes", [])
    if busca:
        b = busca.lower()
        lista = [c for c in lista if
                 b in (c.get("nome") or "").lower() or
                 b in (c.get("cpf") or "").lower() or
                 b in (c.get("telefone") or "").lower()]
    return lista


@router.post("/clientes")
def criar_cliente(cliente: ClienteIn):
    data = _load()
    novo = {"id": _new_id(), "criado_em": _now(), **cliente.model_dump()}
    data["clientes"].append(novo)
    _save(data)
    return novo


@router.put("/clientes/{cid}")
def atualizar_cliente(cid: str, cliente: ClienteIn):
    data = _load()
    for i, c in enumerate(data["clientes"]):
        if c["id"] == cid:
            data["clientes"][i] = {**c, **cliente.model_dump(), "id": cid}
            _save(data)
            return data["clientes"][i]
    raise HTTPException(404, "Cliente não encontrado")


@router.delete("/clientes/{cid}")
def excluir_cliente(cid: str):
    data = _load()
    antes = len(data["clientes"])
    data["clientes"] = [c for c in data["clientes"] if c["id"] != cid]
    if len(data["clientes"]) == antes:
        raise HTTPException(404, "Cliente não encontrado")
    _save(data)
    return {"ok": True}


# ── iniciais ──────────────────────────────────────────────────────────────────

@router.get("/iniciais")
def listar_iniciais(busca: str = "", andamento: str = ""):
    data = _load()
    lista = data.get("iniciais", [])
    if busca:
        b = busca.lower()
        lista = [i for i in lista if
                 b in (i.get("cliente") or "").lower() or
                 b in (i.get("reu") or "").lower() or
                 b in (i.get("objeto") or "").lower()]
    if andamento:
        lista = [i for i in lista if andamento.upper() in (i.get("andamento") or "").upper()]
    return lista


@router.post("/iniciais")
def criar_inicial(inicial: InicialIn):
    data = _load()
    novo = {"id": _new_id(), "criado_em": _now(), **inicial.model_dump()}
    data["iniciais"].append(novo)
    _save(data)
    return novo


@router.put("/iniciais/{iid}")
def atualizar_inicial(iid: str, inicial: InicialIn):
    data = _load()
    for i, item in enumerate(data["iniciais"]):
        if item["id"] == iid:
            data["iniciais"][i] = {**item, **inicial.model_dump(), "id": iid}
            _save(data)
            return data["iniciais"][i]
    raise HTTPException(404, "Inicial não encontrada")


@router.delete("/iniciais/{iid}")
def excluir_inicial(iid: str):
    data = _load()
    antes = len(data["iniciais"])
    data["iniciais"] = [i for i in data["iniciais"] if i["id"] != iid]
    if len(data["iniciais"]) == antes:
        raise HTTPException(404, "Inicial não encontrada")
    _save(data)
    return {"ok": True}


# ── dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard():
    from datetime import date, timedelta
    data = _load()
    hoje = date.today().isoformat()
    em3  = (date.today() + timedelta(days=3)).isoformat()

    processos = data.get("processos", [])
    iniciais  = data.get("iniciais", [])
    clientes  = data.get("clientes", [])

    ativos = [p for p in processos if not p.get("finalizado")]

    prazos_hoje   = [p for p in ativos if p.get("data","")[:10] == hoje]
    prazos_3dias  = [p for p in ativos if hoje < p.get("data","")[:10] <= em3]
    iniciais_pend = [i for i in iniciais if (i.get("andamento","").upper() not in ("PROTOCOLADO","ARQUIVADO"))]

    return {
        "prazos_hoje": prazos_hoje,
        "prazos_3dias": prazos_3dias,
        "iniciais_pendentes": iniciais_pend,
        "total_clientes": len(clientes),
        "total_processos_ativos": len(ativos),
    }
