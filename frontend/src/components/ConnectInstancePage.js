import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';
import { useAuth } from '../hooks/useAuth';

// Ícones
const RefreshIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>;

const ConnectInstancePage = () => {
  const { handleConnectSuccess } = useAuth();

  const [qrImageSrc, setQrImageSrc] = useState(null);
  const [instanceName, setInstanceName] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState('Iniciando...');

  // ✨ 1. Estado para armazenar o qrcount atual
  const [qrCount, setQrCount] = useState(0);

  const pollingRef = useRef(null);
  const mountedRef = useRef(true);

  // ✨ 2. Refs para as funções para evitar stale closures
  // O setInterval sempre chamará a versão MAIS ATUAL destas funções
  const loadQRCodeRef = useRef(null);
  const checkStatusRef = useRef(null);

  // --- Função checkStatus ---
  // ✨ 3. Movida para useCallback para gerenciar dependências
  const checkStatus = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      const { data } = await api.get('/evolution/instance/status');
      if (!mountedRef.current) return;

      if (data.instance) {
        // 1. CONECTADO?
        if (data.instance.state === 'open') {
          console.log("✅ [Connect] Conectado!");
          if (pollingRef.current) clearInterval(pollingRef.current);
          handleConnectSuccess();
          return; // Sucesso, parar tudo.
        }

        // 2. NÃO CONECTADO. O QR CODE MUDOU?
        // Compara o qrcount da API com o qrcount que salvamos no estado
        if (data.instance.qrcount && data.instance.qrcount !== qrCount) {
          console.log(`[Connect] QR Code mudou (API: ${data.instance.qrcount}, Local: ${qrCount}). Buscando novo...`);

          if (pollingRef.current) clearInterval(pollingRef.current);

          // Chama a função de carregar QR Code (pelo ref)
          if (loadQRCodeRef.current) {
            loadQRCodeRef.current();
          }
        }
        // Se não mudou, o polling continua e tentará novamente em 3s
      }
    } catch (e) {
      console.error("[Connect] Erro no checkStatus. Instância pode não existir.", e);
      // Se a instância não existe (ex: 404), o status falha.
      // Devemos carregar o QR Code, pois ele CRIA a instância.
      if (e.response && e.response.status === 404 && loadQRCodeRef.current) {
         console.log("[Connect] Instância não encontrada, chamando loadQRCode.");
         if (pollingRef.current) clearInterval(pollingRef.current);
         loadQRCodeRef.current();
      }
    }
  }, [qrCount, handleConnectSuccess]); // Depende do qrCount ATUAL

  // --- Função loadQRCode ---
  // ✨ 4. Movida para useCallback
  const loadQRCode = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      setIsLoading(true);
      setError('');
      setStatusMessage('Gerando QR Code...');

      const { data } = await api.post('/evolution/instance/create_and_get_qr');

      if (!mountedRef.current) return;

      if (data && data.base64) {
        setQrImageSrc(data.base64);
        if (data.instance) setInstanceName(data.instance);

        // ✨ 5. Salva o qrcount que veio da API no estado
        if (data.qrcount) {
          setQrCount(data.qrcount);
        }

        // Inicia polling (usando o ref para checkStatus)
        if (pollingRef.current) clearInterval(pollingRef.current);
        pollingRef.current = setInterval(() => {
          if (checkStatusRef.current) {
            checkStatusRef.current();
          }
        }, 3000);

      } else if (data && (data.status === 'CONNECTED' || data.state === 'open')) {
         setStatusMessage('Conectado! Aguarde...');
         if (checkStatusRef.current) checkStatusRef.current();
      } else {
         setError('Não foi possível carregar o QR Code.');
      }
    } catch (err) {
      console.error("[Connect] Erro:", err);
      if (mountedRef.current) setError("Erro de conexão com a API.");
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, []); // Sem dependências

  // ✨ 6. Efeito para manter os refs das funções sempre atualizados
  useEffect(() => {
    checkStatusRef.current = checkStatus;
    loadQRCodeRef.current = loadQRCode;
  }, [checkStatus, loadQRCode]);

  // ✨ 7. Efeito Único de Inicialização (Modificado para usar os refs)
  useEffect(() => {
    mountedRef.current = true;

    const startProcess = async () => {
      // 1. Tenta ver se já conecta
      let isConnected = false;
      try {
          const { data } = await api.get('/evolution/instance/status');
          if (data.instance && data.instance.state === 'open') {
              handleConnectSuccess();
              isConnected = true;
          }
      } catch (e) {
          // Ignora o erro (provavelmente 404, instância não existe)
          isConnected = false;
      }

      // 2. Se não conectou, busca o QR
      if (!isConnected && mountedRef.current) {
        if (loadQRCodeRef.current) {
          loadQRCodeRef.current();
        }
      } else if (mountedRef.current) {
        // Já estava conectado
        setIsLoading(false);
      }
    };

    startProcess();

    return () => {
      mountedRef.current = false;
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleConnectSuccess]); // Dependência de mount

  return (
    <div className="login-container">
      {/* O JSX (HTML) permanece o mesmo.
        A única mudança é que o botão "Tentar Novamente" agora chama
        a função 'loadQRCode' que está em useCallback.
      */}
      <div className="login-box" style={{textAlign: 'center', minHeight: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>

        <div className="login-header" style={{marginBottom: '1rem'}}>
            <h2>Conectar WhatsApp</h2>
            {instanceName && <span style={{fontSize: '0.8rem', color: '#4ec9b0'}}>ID: {instanceName}</span>}
        </div>

        {/* ERRO */}
        {error && (
          <div className="error-message" style={{marginBottom: '1rem', width: '100%'}}>
            {error}
            <button onClick={loadQRCode} className="btn-secondary" style={{marginTop: '10px', width: '100%'}}>Tentar Novamente</button>
          </div>
        )}

        {/* CARREGANDO */}
        {isLoading && !error && (
            <div className="loading-animation-card">
                <div className="loading-spinner-icon"></div>
                <p className="fade-in-text" style={{marginTop: '1rem'}}>{statusMessage}</p>
            </div>
        )}

        {/* QR CODE */}
        {!isLoading && !error && qrImageSrc && (
          <div className="qr-code-container-visible">
            <div style={{background: 'white', padding: '10px', borderRadius: '12px', display: 'inline-block'}}>
                <img src={qrImageSrc} alt="QR Code" style={{ width: 260, height: 260, display: 'block' }} />
            </div>
            <p style={{marginTop: '1.5rem', color: '#ccc', fontSize: '0.9rem'}}>
                Abra o WhatsApp &gt; Aparelhos Conectados &gt; Conectar
            </p>
          </div>
        )}

        {/* Botão de segurança (caso raro de não ter QR nem erro) */}
        {!isLoading && !error && !qrImageSrc && (
            <div style={{padding: '2rem'}}>
                <p style={{marginBottom: '1rem'}}>Nenhum código gerado.</p>
                <button onClick={loadQRCode} className="btn-primary">
                    <RefreshIcon /> Gerar Novo
                </button>
            </div>
        )}
      </div>
      <div className="animated-background-lines">
          <div className="line"></div><div className="line"></div><div className="line"></div>
      </div>
    </div>
  );
};

export default ConnectInstancePage;