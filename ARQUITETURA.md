# Documento de Arquitetura - Cosmos Copilot v2.0

**Versão:** 2.0
**Data da Última Atualização:** 07/10/2025

## 1. Visão Geral

O Cosmos Copilot v2.0 é um Assistente de Vendas com IA Estratégica, projetado para atuar como um parceiro proativo para a equipe comercial. Sua função é analisar mensagens específicas da conversa (iniciadas por uma ação do vendedor) e fornecer sugestões de resposta contextuais e estratégicas, com o objetivo de guiar o cliente por um funil de vendas pré-definido.

O sistema opera em tempo real, sendo acionado pelo vendedor para analisar o contexto da conversa e sugerir os próximos passos, visando aumentar a eficiência, padronizar a abordagem e acelerar o fechamento de negócios.

## 2. A Arquitetura dos "4 Cérebros"

O sistema é fundamentado em uma arquitetura de múltiplos contextos, onde uma IA Orquestradora central consulta três "cérebros" de conhecimento especializados para tomar decisões.

### Cérebro 1: O Especialista do Produto (RAG Técnico)
* **Propósito:** Sabe **O QUE** o sistema faz e **COMO** faz. Contém o conhecimento factual sobre o CosmosERP.
* **Implementação:**
    * Um banco de dados vetorial **ChromaDB** (`backend/chroma_db_local/`).
    * Alimentado por arquivos `.jsonl` (`backend/data/refinado_*.jsonl`).
    * Gerenciado pelo script `backend/scripts/gerenciar_pipeline.py`.

### Cérebro 2: O Especialista do Cliente (RAG Conversacional)
* **Propósito:** Sabe **QUEM** é o cliente e **O QUE** já foi dito. Mantém a memória de cada conversa.
* **Implementação:**
    * Bancos de dados vetoriais **ChromaDB** individuais para cada conversa (`backend/chroma_db_conversas/convo_{id}`).
    * Alimentado em tempo real pelas mensagens do cliente (via webhook da Evolution API) e do vendedor (via chamada da API pelo frontend).
    * Gerenciado pelas funções `get_or_create_conversation_db`, `add_message_to_conversation_rag`, `get_client_data_from_memory` e `get_conversation_tone` no `core/cerebro_ia.py`.

### Cérebro 3: O Estrategista de Vendas (Playbook de Vendas)
* **Propósito:** Sabe **POR QUÊ** e **PARA ONDE** guiar a conversa. Contém a estratégia comercial e a rota de venda.
* **Implementação:**
    * Um arquivo de configuração central: `backend/data/playbook_vendas.json`.
    * Define os estágios da conversa (`stages`), as ações a serem tomadas (`action`), os templates de resposta com múltiplos tons (`suggestion.tones`) e as opções de próximo passo (`next_options`).

### O Orquestrador Central (LLM)
* **Propósito:** É a inteligência principal que une tudo. Ele consulta os outros três cérebros para entender o cenário completo e formular a sugestão estratégica.
* **Implementação:**
    * A função `generate_sales_suggestions` no arquivo `backend/core/cerebro_ia.py`.
    * Utiliza um modelo de linguagem avançado (Gemini) e múltiplos prompts (`TRIAGE_PROMPT`, `INTENT_PROMPT`, etc.) para tomar decisões.

## 3. Fluxo de Dados e Lógica

### 3.1. Pipeline de Ingestão de Conhecimento (`gerenciar_pipeline.py`)
Este script constrói e mantém o **Cérebro 1**. O fluxo é orientado a item (vídeo por vídeo) para eficiência.
1.  **Entrada:** Lista de URLs no `youtube_links.txt`.
2.  **Transcrição:** Usa o Whisper para transcrever novos vídeos, criando um arquivo `.json` como cache permanente.
3.  **Refinamento:** Usa uma IA (Gemini) para ler as transcrições e gerar "chunks de conhecimento" estruturados em formato `.jsonl`, com título, conteúdo e metadados ricos (timestamps, módulo, tags, tipo de fonte).
4.  **Indexação:** Lê todos os arquivos `.jsonl` e os armazena no ChromaDB principal, criando os vetores de embedding.

### 3.2. Geração de Sugestão (Fluxo em Tempo Real)

Este é o fluxo que ocorre a cada vez que o vendedor solicita uma sugestão.
1.  **Gatilho (Frontend):** O vendedor clica e arrasta uma mensagem do cliente e a solta no Painel do Copiloto.
2.  **Requisição (`App.js` -> `main.py`):** O frontend envia uma requisição `POST /generate_response` contendo: `query` (o texto da mensagem arrastada), `conversation_id` e `current_stage_id`.
3.  **Orquestração (`core/cerebro_ia.py`):** A função `generate_sales_suggestions` executa a seguinte sequência:
    a. **Análise de Tom:** Consulta o **RAG Conversacional (Cérebro 2)** para detectar o tom geral do cliente (formal, amigável, etc.).
    b. **Triagem de Intenção:** Usa o `TRIAGE_PROMPT` para classificar a `query` (ex: `pergunta_tecnica`, `resposta_qualificacao`, `comentario_geral`).
    c. **Decisão de Fluxo:** Com base na `triagem`, decide qual caminho seguir:
        * Se for um `comentario_geral`, retorna uma sugestão vazia ("Silêncio Inteligente").
        * Se for uma `resposta_qualificacao`, aciona o fluxo de extração e memorização de dados do cliente.
        * Se for uma `pergunta_tecnica`, aciona o fluxo do funil de vendas.
    d. **Transição de Estágio:** Consulta o **Playbook de Vendas (Cérebro 3)** para determinar o `next_stage_id` com base no estágio atual e na intenção.
    e. **Execução da Ação:** Executa a `action` do novo estágio (ex: consultar o **RAG Técnico (Cérebro 1)** para encontrar um vídeo).
    f. **Leitura da Memória:** Consulta o **RAG Conversacional (Cérebro 2)** via `get_client_data_from_memory` para obter dados como `{cliente_nome}` e `{empresa_cliente}` para personalizar a resposta.
    g. **Montagem da Resposta:** Pega os `tones` do estágio atual do playbook, marca a opção recomendada com base no tom detectado, e monta a resposta final em JSON estruturado, contendo o `new_stage_id` e as múltiplas `text_options`.
4.  **Renderização no Frontend (`CopilotPanel.js`):** O frontend recebe a resposta estruturada e renderiza um card de sugestão "inteligente" com um seletor de tons, destacando a opção recomendada.

## 4. Estrutura de Arquivos Principal

backend/
├── core/
│   ├── init.py
│   └── cerebro_ia.py         # Orquestrador, lógica principal da IA (Cérebro 3)
├── data/
│   ├── refinado_.jsonl      # Conhecimento processado (para o Cérebro 1)
│   ├── youtube_.json        # Cache de transcrições
│   ├── playbook_vendas.json    # Cérebro Estratégico (Cérebro 4)
│   └── youtube_links.txt     # Lista de fontes de conhecimento
├── scripts/
│   ├── init.py
│   └── gerenciar_pipeline.py # Ferramenta para construir o Cérebro 1
├── chroma_db_local/          # Banco de Dados do Cérebro 1
├── chroma_db_conversas/      # Bancos de Dados do Cérebro 2
├── main.py                   # Servidor da API (FastAPI)
└── diagnostico_rag_final.py  # Script para testar a qualidade do Cérebro 1


## 5. Plano de Manutenção

Este é um documento vivo. A cada mudança significativa na arquitetura ou adição de uma nova funcionalidade, este documento deve ser revisado e atualizado.