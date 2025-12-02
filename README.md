# Cosmos Copilot 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-009688.svg)](https://fastapi.tiangolo.com/)

> **Select Language / Selecione o Idioma:**
>
> 🇺🇸 [**English**](#english) | 🇧🇷 [**Português**](#português)

---

<a name="english"></a>
## 🇺🇸 English

### Overview

**Cosmos Copilot** is an advanced AI-powered Sales Assistant designed to revolutionize how sales teams interact with customers on WhatsApp. By bridging real-time messaging with Large Language Models (LLMs), Cosmos Copilot acts as a "second brain" for sellers, providing real-time suggestions, sentiment analysis, and automated context retrieval to close deals faster.

This project demonstrates a robust implementation of **Agentic AI** workflows, real-time **WebSockets**, and **Microservices** architecture.

### Key Features

*   **🤖 Real-Time AI Copilot**: Analyzes incoming WhatsApp messages instantly and suggests the best professional responses based on sales playbooks and product knowledge.
*   **💬 Seamless WhatsApp Integration**: Powered by **Evolution API** to handle WhatsApp Web protocols, ensuring stable and reliable messaging.
*   **🧠 RAG (Retrieval-Augmented Generation)**: Uses **ChromaDB** to store and retrieve vector embeddings of product catalogs, ensuring the AI answers with accurate, business-specific data.
*   **⚡ Real-Time Updates**: Built with **WebSockets** to push messages, reactions, and AI insights to the frontend instantly without polling.
*   **📊 Sales Context Analysis**: Automatically analyzes conversation history to determine the "temperature" of the lead and suggest the next best action.
*   **🏢 Multi-Tenant Architecture**: Designed to support multiple companies and sales teams within a single deployment.

### Tech Stack

*   **Frontend**: React.js, Context API, CSS Modules (Custom Design System).
*   **Backend**: Python, FastAPI, Uvicorn.
*   **AI & Data**: LangChain, OpenAI/Gemini APIs, ChromaDB (Vector Store).
*   **Infrastructure**: Docker, Google Cloud Run, Redis (Caching), Nginx.
*   **DevOps**: CI/CD Pipelines (Cloud Build), Environment Management.

### System Architecture

```mermaid
graph TD
    Client([Customer WhatsApp]) <-->|Messages| WhatsAppServer
    WhatsAppServer <-->|Protocol| EvolutionAPI[Evolution API Service]
    
    subgraph "Cosmos Backend Cloud"
        EvolutionAPI -->|Webhook| FastAPI[FastAPI Backend]
        FastAPI -->|Pub/Sub| WebSocketMgr[WebSocket Manager]
        FastAPI <-->|Cache| Redis[(Redis Cache)]
        FastAPI <-->|Vectors| ChromaDB[(ChromaDB RAG)]
        FastAPI <-->|Inference| LLM[LLM Service (GPT/Gemini)]
    end
    
    subgraph "Seller Dashboard"
        WebSocketMgr -->|Real-time Events| ReactApp[React Frontend]
        ReactApp -->|Actions| FastAPI
    end
```

### Getting Started

1.  **Clone the repository**
    ```bash
    git clone https://github.com/your-username/cosmos-copilot.git
    ```

2.  **Backend Setup**
    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-backend.txt
    uvicorn main:app --reload
    ```

3.  **Frontend Setup**
    ```bash
    cd frontend
    npm install
    npm start
    ```

---

<a name="português"></a>
## 🇧🇷 Português

### Visão Geral

**Cosmos Copilot** é um Assistente de Vendas avançado impulsionado por IA, projetado para otimizar a comunicação de equipes de vendas no WhatsApp. Unindo mensageria em tempo real com Grandes Modelos de Linguagem (LLMs), o Cosmos atua como um "segundo cérebro" para o vendedor, fornecendo sugestões em tempo real, análise de sentimento e recuperação automática de contexto para fechar negócios mais rápido.

Este projeto demonstra uma implementação robusta de fluxos de **IA Agêntica**, **WebSockets** em tempo real e arquitetura de **Microsserviços**.

### Funcionalidades Principais

*   **🤖 Copilot de IA em Tempo Real**: Analisa mensagens recebidas no WhatsApp instantaneamente e sugere as melhores respostas profissionais baseadas em playbooks de vendas.
*   **💬 Integração Fluida com WhatsApp**: Utiliza a **Evolution API** para gerenciar protocolos do WhatsApp Web, garantindo estabilidade.
*   **🧠 RAG (Geração Aumentada por Recuperação)**: Usa **ChromaDB** para armazenar e buscar embeddings vetoriais de catálogos de produtos, garantindo que a IA responda com dados precisos da empresa.
*   **⚡ Atualizações em Tempo Real**: Construído com **WebSockets** para enviar mensagens, reações e insights da IA para o frontend instantaneamente, sem recarregamentos.
*   **📊 Análise de Contexto de Vendas**: Analisa automaticamente o histórico da conversa para determinar a "temperatura" do lead e sugerir a próxima melhor ação.
*   **🏢 Arquitetura Multi-Tenant**: Projetado para suportar múltiplas empresas e times de vendas em uma única implantação.

### Stack Tecnológico

*   **Frontend**: React.js, Context API, CSS Modules (Design System Próprio).
*   **Backend**: Python, FastAPI, Uvicorn.
*   **IA & Dados**: LangChain, OpenAI/Gemini APIs, ChromaDB (Vector Store).
*   **Infraestrutura**: Docker, Google Cloud Run, Redis (Caching), Nginx.
*   **DevOps**: Pipelines CI/CD (Cloud Build), Gerenciamento de Ambientes.

### Arquitetura do Sistema

```mermaid
graph TD
    Client([Cliente WhatsApp]) <-->|Mensagens| WhatsAppServer
    WhatsAppServer <-->|Protocolo| EvolutionAPI[Serviço Evolution API]
    
    subgraph "Cosmos Backend Cloud"
        EvolutionAPI -->|Webhook| FastAPI[Backend FastAPI]
        FastAPI -->|Pub/Sub| WebSocketMgr[Gerenciador WebSocket]
        FastAPI <-->|Cache| Redis[(Redis Cache)]
        FastAPI <-->|Vetores| ChromaDB[(ChromaDB RAG)]
        FastAPI <-->|Inferência| LLM[Serviço LLM (GPT/Gemini)]
    end
    
    subgraph "Dashboard do Vendedor"
        WebSocketMgr -->|Eventos Real-time| ReactApp[Frontend React]
        ReactApp -->|Ações| FastAPI
    end
```

### Como Iniciar

1.  **Clone o repositório**
    ```bash
    git clone https://github.com/seu-usuario/cosmos-copilot.git
    ```

2.  **Configuração do Backend**
    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-backend.txt
    uvicorn main:app --reload
    ```

3.  **Configuração do Frontend**
    ```bash
    cd frontend
    npm install
    npm start
    ```

---

### Author / Autor

Developed with ❤️ by **Osvaldo Duarte**.
*Building the future of AI-driven sales.*