# Cosmos Copilot

Assistente de vendas com IA para otimizar a comunicação com clientes via WhatsApp.

---

## 🚀 Configuração do Ambiente de Desenvolvimento

Siga estes passos para configurar o projeto na sua máquina local.

### Pré-requisitos
* Python 3.9+ e Node.js 18+
* Acesso ao projeto no Google Cloud Platform (fale com o Tech Lead).
* [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) instalado e autenticado.

### Passo a Passo

1.  **Clone o Repositório**
    ```bash
    git clone [https://github.com/seu-usuario/cosmos-copilot.git](https://github.com/seu-usuario/cosmos-copilot.git)
    cd cosmos-copilot
    ```

2.  **Configure o Backend (Python)**
    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate  # No Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configure o Frontend (React)**
    ```bash
    cd ../frontend
    npm install
    ```

4.  **Baixe os Ativos de Dados**
    A base de conhecimento para o RAG é gerenciada no Google Cloud Storage para manter o repositório leve. Use o `gcloud CLI` para baixar os dados necessários.

    ```bash
    # Volte para a raiz do backend
    cd ../backend

    # Baixe o arquivo de dados do nosso bucket
    gsutil cp gs://cosmos-copilot-data-assets/data.zip .

    # Descompacte o arquivo (no Linux/macOS)
    unzip data.zip

    # (No Windows, use o Explorer para descompactar)
    ```
    Após descompactar, você deve ter uma pasta `data/` dentro da pasta `backend/`.

5.  **Gere a Base Vetorial Local**
    Com os dados no lugar, execute a pipeline para criar o banco de dados vetorial que a IA irá usar.
    ```bash
    # Certifique-se de que seu ambiente virtual (.venv) está ativo
    python scripts/gerenciar_pipeline.py
    ```

6.  **Inicie os Servidores**
    * **Backend:** Na pasta `backend`, execute: `uvicorn main:app --reload`
    * **Frontend:** Em outro terminal, na pasta `frontend`, execute: `npm start`

---