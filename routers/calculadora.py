from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import date
from typing import List, Optional
from core.indices import load_indices, update_indices
from core.calculos import calculate_charge

router = APIRouter()


class Lancamento(BaseModel):
    data_cobranca: date
    valor: float


class CalculoRequest(BaseModel):
    lancamentos: List[Lancamento]
    data_calculo: date
    tribunal: str = "TJMG"
    honorarios_pct: float = 20.0
    multa_523: bool = False
    modo: str = "execucao"  # "execucao" ou "inicial"
    aplicar_dobro: bool = False
    dano_moral: float = 0.0


class IndicesStatus(BaseModel):
    ultima_atualizacao: Optional[str]
    tem_inpc: bool
    tem_ipcae: bool
    tem_selic: bool
    tem_tjsp_inpc: bool
    tem_tjsp_14905: bool


@router.get("/indices/status", response_model=IndicesStatus)
def indices_status():
    idx = load_indices()
    return IndicesStatus(
        ultima_atualizacao=idx.get("ultima_atualizacao"),
        tem_inpc=bool(idx.get("inpc")),
        tem_ipcae=bool(idx.get("ipcae")),
        tem_selic=bool(idx.get("selic")),
        tem_tjsp_inpc=bool(idx.get("tjsp_inpc")),
        tem_tjsp_14905=bool(idx.get("tjsp_14905")),
    )


@router.post("/indices/atualizar")
def atualizar_indices(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_indices)
    return {"mensagem": "Atualização iniciada em background"}


@router.post("/calcular")
def calcular(req: CalculoRequest):
    indices = load_indices()
    if not indices.get("inpc"):
        raise HTTPException(status_code=400, detail="Índices não carregados. Atualize os índices primeiro.")

    rows = []
    subtotal_principal = 0.0
    subtotal_juros = 0.0

    for lanc in req.lancamentos:
        result = calculate_charge(
            lanc.valor, lanc.data_cobranca, req.data_calculo, indices, req.tribunal
        )
        rows.append({
            "data_cobranca": lanc.data_cobranca.strftime("%d/%m/%Y"),
            "valor_original": lanc.valor,
            "fator_correcao": result["correction_factor"],
            "debito_corrigido": result["corrected"],
            "juros_pct": result["interest_pct"],
            "juros_valor": result["interest_value"],
            "total": result["total"],
            "meses": result["months"],
        })
        subtotal_principal += result["corrected"]
        subtotal_juros += result["interest_value"]

    subtotal_base = subtotal_principal + subtotal_juros

    if req.modo == "inicial":
        subtotal_material = subtotal_base * 2 if req.aplicar_dobro else subtotal_base
        total_geral = subtotal_material + req.dano_moral
        summary = {
            "subtotal_principal": round(subtotal_principal, 2),
            "subtotal_juros": round(subtotal_juros, 2),
            "subtotal_base": round(subtotal_base, 2),
            "subtotal_material": round(subtotal_material, 2),
            "aplicar_dobro": req.aplicar_dobro,
            "dano_moral": round(req.dano_moral, 2),
            "total_geral": round(total_geral, 2),
        }
    else:
        honorarios_valor = subtotal_base * req.honorarios_pct / 100.0
        subtotal_com_honorarios = subtotal_base + honorarios_valor
        multa_valor = subtotal_com_honorarios * 0.10 if req.multa_523 else 0.0
        total_geral = subtotal_com_honorarios + multa_valor
        summary = {
            "subtotal_principal": round(subtotal_principal, 2),
            "subtotal_juros": round(subtotal_juros, 2),
            "subtotal_base": round(subtotal_base, 2),
            "honorarios_pct": req.honorarios_pct,
            "honorarios_valor": round(honorarios_valor, 2),
            "multa_523": req.multa_523,
            "multa_valor": round(multa_valor, 2),
            "total_geral": round(total_geral, 2),
        }

    return {"rows": rows, "summary": summary, "tribunal": req.tribunal}
