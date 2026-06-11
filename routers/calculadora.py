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


# ── Execução de Honorário ──────────────────────────────────────

class HonorarioRequest(BaseModel):
    valor_causa: float
    data_origem: date
    data_calculo: date
    tribunal: str = "TJMG"
    honorarios_pct: float = 20.0
    numero_processo: str = ""


@router.post("/honorario")
def calcular_honorario(req: HonorarioRequest):
    from core.calculos import iter_months, get_correction_index, calc_correcao_tjsp
    indices = load_indices()
    if not indices.get("inpc"):
        raise HTTPException(status_code=400, detail="Índices não carregados.")
    if req.data_origem >= req.data_calculo:
        raise HTTPException(status_code=400, detail="Data de origem deve ser anterior à data do cálculo.")

    is_tjsp = "TJSP" in req.tribunal
    if is_tjsp:
        valor_corrigido, corr_factor, meses_corr = calc_correcao_tjsp(
            req.valor_causa, req.data_origem, req.data_calculo, indices)
        indice_label = "Tabela Prática TJSP"
    else:
        corr_factor = 1.0; meses_corr = 0; indices_usados = []
        for year, month in iter_months(req.data_origem, req.data_calculo):
            corr_factor *= 1.0 + get_correction_index(year, month, indices) / 100.0
            meses_corr += 1
            indices_usados.append("INPC" if (year < 2024 or (year == 2024 and month <= 8)) else "IPCAe")
        valor_corrigido = round(req.valor_causa * corr_factor, 2)
        if not indices_usados:
            indice_label = "INPC"
        elif all(i == "INPC" for i in indices_usados):
            indice_label = "INPC"
        elif all(i == "IPCAe" for i in indices_usados):
            indice_label = "IPCAe"
        else:
            indice_label = "INPC/IPCAe"

    variacao_pct = round((corr_factor - 1.0) * 100, 4)
    honorario_valor = round(valor_corrigido * req.honorarios_pct / 100.0, 2)

    return {
        "valor_original": req.valor_causa,
        "valor_corrigido": valor_corrigido,
        "corr_factor": round(corr_factor, 6),
        "variacao_pct": variacao_pct,
        "meses_corr": meses_corr,
        "indice_label": indice_label,
        "honorarios_pct": req.honorarios_pct,
        "honorario_valor": honorario_valor,
        "periodo": f"{req.data_origem.strftime('%d/%m/%Y')} a {req.data_calculo.strftime('%d/%m/%Y')}",
        "numero_processo": req.numero_processo,
    }


# ── Revisional de Veículo / Empréstimo ───────────────────────

class RevisionalRequest(BaseModel):
    tipo: str = "veiculo"      # "veiculo" ou "emprestimo"
    pv: float                   # valor financiado
    pmt_contratada: float       # parcela contratada
    n_parcelas: int             # total de parcelas
    data_contratacao: date
    data_calculo: date
    taxa_bacen: Optional[float] = None  # % a.m. — se None, usa taxa implícita como referência


def _pmt(pv: float, i_pct: float, n: int) -> float:
    if n == 0: return 0.0
    i = i_pct / 100.0
    if i == 0: return pv / n
    return pv * i / (1 - (1 + i) ** (-n))


def _taxa_implicita(pv: float, pmt: float, n: int) -> Optional[float]:
    if pv <= 0 or pmt <= 0 or n <= 0: return None
    i = (pmt * n / pv - 1) / n
    if i <= 0: i = 0.01
    for _ in range(1000):
        fi = pmt - pv * i / (1 - (1 + i) ** (-n))
        dfi_denom = (1 - (1 + i) ** (-n)) ** 2
        if abs(dfi_denom) < 1e-15: break
        dfi = -pv * ((1 - (1 + i) ** (-n)) - i * n * (1 + i) ** (-n - 1)) / dfi_denom
        if abs(dfi) < 1e-15: break
        i_novo = i - fi / dfi
        if i_novo <= 0: i_novo = i / 2
        if abs(i_novo - i) < 1e-10: i = i_novo; break
        i = i_novo
    return i * 100.0 if i > 0 else None


@router.post("/revisional")
def calcular_revisional(req: RevisionalRequest):
    taxa_contratada = _taxa_implicita(req.pv, req.pmt_contratada, req.n_parcelas)
    if taxa_contratada is None:
        raise HTTPException(status_code=400, detail="Não foi possível calcular a taxa implícita.")

    taxa_referencia = req.taxa_bacen if req.taxa_bacen else taxa_contratada * 0.6  # fallback estimate
    pmt_justa = _pmt(req.pv, taxa_referencia, req.n_parcelas)
    excesso_mensal = req.pmt_contratada - pmt_justa

    # Parcelas até hoje
    from dateutil.relativedelta import relativedelta
    parcelas = []
    total_excesso_corrigido = 0.0
    data_atual = req.data_contratacao
    for k in range(req.n_parcelas):
        data_venc = data_atual + relativedelta(months=k + 1)
        exc = max(0.0, excesso_mensal)
        parcelas.append({
            "parcela": k + 1,
            "data_vencimento": data_venc.strftime("%d/%m/%Y"),
            "pmt_contratada": round(req.pmt_contratada, 2),
            "pmt_justa": round(pmt_justa, 2),
            "excesso": round(exc, 2),
        })
        total_excesso_corrigido += exc

    return {
        "tipo": req.tipo,
        "pv": req.pv,
        "n_parcelas": req.n_parcelas,
        "taxa_contratada_pct": round(taxa_contratada, 4),
        "taxa_referencia_pct": round(taxa_referencia, 4),
        "pmt_contratada": req.pmt_contratada,
        "pmt_justa": round(pmt_justa, 2),
        "excesso_mensal": round(excesso_mensal, 2),
        "total_excesso": round(total_excesso_corrigido, 2),
        "parcelas": parcelas[:12],  # first 12 for preview
        "total_parcelas": len(parcelas),
    }
