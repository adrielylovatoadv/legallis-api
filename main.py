from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import calculadora, controle, financeiro

app = FastAPI(title="Legallis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "https://app.legallis.app.br"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(calculadora.router, prefix="/calculadora", tags=["Calculadora"])
app.include_router(controle.router, prefix="/controle", tags=["Controle Processual"])
app.include_router(financeiro.router, prefix="/financeiro", tags=["Financeiro"])

@app.get("/")
def health():
    return {"status": "ok", "service": "legallis-api"}
