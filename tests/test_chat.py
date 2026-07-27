"""Testes de core/chat.py com FakeLLMClient — sem I/O, sem chamada de API."""

from __future__ import annotations

from pmo_assistant.core.chat import responder_pergunta
from tests.conftest import FakeLLMClient

TRECHOS = [
    {"texto": "A NETCON ficou responsável por enviar o cronograma até 03/12.", "documento_id": 1},
    {"texto": "O escopo inclui substituição de transformadores.", "documento_id": 1},
]


def test_responder_pergunta_sem_trechos_nao_chama_llm() -> None:
    llm = FakeLLMClient(payload={})
    resposta = responder_pergunta("Qual o prazo?", [], "Projeto Charqueadas", llm)
    assert resposta.confianca == 0.0
    assert resposta.fontes == []
    assert llm.chamadas == []


def test_responder_pergunta_feliz() -> None:
    llm = FakeLLMClient(
        payload={
            "resposta": 'A NETCON deve enviar o cronograma até 03/12, conforme: "A NETCON ficou responsável por enviar o cronograma até 03/12."',
            "fontes": ["A NETCON ficou responsável por enviar o cronograma até 03/12."],
            "confianca": 0.9,
        }
    )
    resposta = responder_pergunta("Qual o prazo do cronograma?", TRECHOS, "Projeto Charqueadas", llm)
    assert "03/12" in resposta.resposta
    assert resposta.fontes
    assert resposta.confianca == 0.9
    assert len(llm.chamadas) == 1
    assert "Projeto Charqueadas" in llm.chamadas[0]["user"]
    assert llm.chamadas[0]["ferramenta"] == "registrar_resposta"


def test_responder_pergunta_inclui_trechos_no_prompt() -> None:
    llm = FakeLLMClient(payload={"resposta": "x", "fontes": [], "confianca": 0.5})
    responder_pergunta("pergunta qualquer", TRECHOS, "contexto", llm)
    user_prompt = llm.chamadas[0]["user"]
    assert "NETCON" in user_prompt
    assert "transformadores" in user_prompt
