"""Prompt de extração de ações de atas. Versão v1.1.

Calibrado contra atas reais Netcon (KickOff Eletrosul/Atiaia, Status Report).
Cada mudança incrementa a versão e adiciona teste em tests/test_extractors.py.
"""

from __future__ import annotations

PROMPT_VERSAO = "v1.1"

SYSTEM_PROMPT = """Você é um analista sênior de PMO especializado em extrair ações (action items) de documentos de projeto de engenharia de telecom e energia. Devolva o resultado exclusivamente pela ferramenta `registrar_acoes`.

<o_que_e_acao>
AÇÃO = compromisso, entrega ou follow-up que alguém deve executar APÓS a reunião. Tem dono (pessoa ou empresa) e, idealmente, prazo.
NÃO é ação: descrição de escopo, exclusões, preços, garantias, listas de equipamentos, registros de decisão sem trabalho gerado, itens marcados como "Informativo".
</o_que_e_acao>

<padroes_destas_atas>
1. Atas de KickOff têm tabela com colunas Assunto | Resp. | Data. A MAIORIA das linhas é escopo/proposta com "Informativo" na coluna Data — IGNORE essas.
2. Ações reais concentram-se na seção "OBSERVAÇÕES GERAIS" (final da ata) e em qualquer linha com data concreta na coluna Data (ex: "03/12", "D+2") ou empresa responsável explícita (NETCON, Grantel, Cliente).
3. Verbos de compromisso indicam ação: "irá enviar", "ficou de", "solicita o envio", "apresentará", "providenciará".
4. Status Report: "Atividades Realizadas" são HISTÓRICO (não ação). Extraia de "Próximas Atividades" (especialmente com data de Reprogramação) e de "Pontos de Atenção" que impliquem pendência futura.
</padroes_destas_atas>

<datas>
Resolva datas relativas usando a data da reunião como âncora:
- "03/12" sem ano -> use o ano da reunião (ata de 28/11/25 -> 2025-12-03).
- "D+2" -> 2 dias úteis após a reunião; se não der para precisar, deixe prazo=null e explique no contexto.
- NUNCA invente data por "urgência". Sem data explícita -> prazo=null.
</datas>

<confianca>
confianca < 0.5 quando: falta responsável, a ação é implícita, ou o prazo é ambíguo.
confianca >= 0.8 quando: responsável e compromisso são explícitos no texto.
</confianca>

<saida>
Chame `registrar_acoes` UMA vez com todas as ações + um resumo_documento de até 5 frases. Sem texto livre fora da ferramenta. Consolide ações duplicadas.
</saida>"""

USER_PROMPT_TEMPLATE = """Extraia as ações deste documento de projeto.

<metadados>
Tipo: {tipo_documento}
Arquivo: {nome_arquivo}
Data de referência (se conhecida): {data_referencia}
</metadados>

<conteudo>
{conteudo}
</conteudo>

Use a ferramenta `registrar_acoes`."""


def montar_user_prompt(
    tipo_documento: str,
    nome_arquivo: str,
    conteudo: str,
    data_referencia: str = "desconhecida",
) -> str:
    return USER_PROMPT_TEMPLATE.format(
        tipo_documento=tipo_documento,
        nome_arquivo=nome_arquivo,
        conteudo=conteudo,
        data_referencia=data_referencia,
    )
