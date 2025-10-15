# 🚀 Cosmos Copilot - Assistente de Vendas com IA

O Cosmos Copilot é um assistente de vendas inteligente projetado para capacitar a equipe comercial, fornecendo sugestões de resposta em tempo real diretamente em conversas do WhatsApp.

Integrado à **Evolution API**, o Copilot utiliza um sistema de múltiplos "cérebros" (RAG) para entender o contexto da conversa, consultar a base de conhecimento de produtos, seguir um playbook de vendas estratégico e, finalmente, gerar respostas relevantes e eficazes.

## ✨ Funcionalidades Principais

-   **Interface Reativa:** Um painel de controle que exibe conversas do WhatsApp em tempo real.
-   **Sugestões Inteligentes:** Arraste uma mensagem do cliente para o painel do Copilot para receber sugestões instantâneas de resposta.
-   **Arquitetura Multi-Cérebro:**
    -   **Cérebro 1 (Produto):** Base de conhecimento vetorial sobre o CosmosERP.
    -   **Cérebro 2 (Cliente):** Memória persistente do histórico de cada conversa.
    -   **Cérebro 3 (Estratégia):** Lógica de vendas baseada em um playbook customizável.
    -   **Cérebro 4 (Conteúdo):** Sugestão de vídeos e materiais de apoio.
-   **Início Proativo de Conversas:** Funcionalidade para iniciar um novo chat com um cliente diretamente da interface.

## 🛠️ Tecnologias Utilizadas

-   **Backend:** Python, FastAPI
-   **Frontend:** React.js
-   **Base de Conhecimento (RAG):** ChromaDB, LangChain
-   **Integração WhatsApp:** Evolution API
-   **Orquestração:** Docker & Docker Compose

---

## 🏁 Guia de Instalação e Execução

Siga os passos abaixo para configurar e rodar o projeto em seu ambiente local.

### 1. Pré-requisitos

-   **Docker** e **Docker Compose**
-   **Node.js** (versão 18 ou superior)
-   **Python** (versão 3.11 ou superior)

### 2. Configuração do Ambiente

1.  **Clone o Repositório:**
    ```bash
    git clone [https://github.com/osvaldoduarte/cosmos-copilot.git](https://github.com/osvaldoduarte/cosmos-copilot.git)
    cd cosmos-copilot
    ```

2.  **Configure a Evolution API:**
    -   Navegue até o diretório raiz do projeto.
    -   Crie uma cópia do arquivo de exemplo `.env.example` e renomeie-a para `.env`.
    -   Abra o arquivo `.env` e preencha as variáveis da `EVOLUTION_API`, principalmente a sua `EVOLUTION_API_KEY`.

3.  **Configure as Chaves da IA:**
    -   Dentro da pasta `backend/`, crie um arquivo `.env`.
    -   Adicione sua chave da OpenAI (ou outro provedor de LLM) neste arquivo:
        ```env
        OPENAI_API_KEY="sua_chave_aqui"
        ```

### 3. Executando a Aplicação

A execução é dividida em três serviços principais: a API do WhatsApp, o nosso backend e o frontend.

1.  **Inicie a Evolution API (via Docker):**
    No terminal, a partir da raiz do projeto, execute:
    ```bash
    docker-compose up -d
    ```
    -   Este comando irá baixar a imagem da Evolution API e iniciá-la em segundo plano.
    -   Acesse `http://localhost:8080` no seu navegador para escanear o QR Code e conectar seu número de WhatsApp. O banco de dados para persistir as conversas será criado automaticamente.

2.  **Inicie o Backend (Python):**
    Abra um **novo terminal**.
    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    uvicorn main:app --reload
    ```

3.  **Inicie o Frontend (React):**
    Abra um **terceiro terminal**.
    ```bash
    cd frontend
    npm install
    npm start
    ```

### 4. Geração da Base de Conhecimento (Passo Único)

Após iniciar todos os serviços pela primeira vez, você precisa popular a base de conhecimento da IA.

-   Abra um **quarto terminal**.
-   Navegue até a pasta `backend/` e ative o ambiente virtual:
    ```bash
    cd backend
    source .venv/bin/activate
    ```
-   Execute o script de pipeline:
    ```bash
    python scripts/gerenciar_pipeline.py
    ```
    -   Este script irá processar os documentos e vídeos, criando os bancos de dados vetoriais que a IA utiliza. **Você só precisa executar isso uma vez** ou quando a base de conhecimento for atualizada.

---

Agora, acesse `http://localhost:3000` em seu navegador. O Cosmos Copilot estará pronto para uso!