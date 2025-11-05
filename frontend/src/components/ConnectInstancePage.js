import React, { useState, useEffect, useRef, useCallback } from 'react';
import api from '../services/api';

function ConnectInstancePage({ onConnectSuccess }) {
  const [qrImageSrc, setQrImageSrc] = useState(null);
  const [instanceName, setInstanceName] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState('Verificando status da conexão...');

  const pollingIntervalRef = useRef(null);

  // --- 💡 CORREÇÃO 1/4: Função envolvida em useCallback ---
  const checkStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/evolution/instance/status');

      // --- 💡 CORREÇÃO 2/4: Lendo data.instance.state ---
      if (data.instance && data.instance.state === 'open') {
        console.log("ConnectInstancePage: Conectado! Redirecionando...");
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
        onConnectSuccess();
        return true;
      } else {
        const status = data.instance ? data.instance.state : 'desconhecido';
        console.log(`ConnectInstancePage: Ainda não conectado, status: ${status}`);
        setStatusMessage(`Aguardando conexão... (Status: ${status})`);
        return false;
      }
    } catch (err) {
      console.error("Erro no polling de status:", err);
      return false;
    }
  }, [onConnectSuccess]); // Depende apenas de onConnectSuccess (que agora é estável)


  // --- 💡 CORREÇÃO 3/4: Função envolvida em useCallback ---
  const fetchQRCode = useCallback(async () => {
    try {
      setError('');
      setStatusMessage('Instância desconectada. Gerando QR Code...');
      setQrImageSrc(null);

      const { data } = await api.post('/evolution/instance/create_and_get_qr');

      if (data && data.base64) {
        setQrImageSrc(data.base64);
        setStatusMessage('Escaneie o QR Code para conectar.');
        if (data.instance) {
            setInstanceName(data.instance);
        }
      } else {
         setStatusMessage(`Status da instância: ${data.status || 'desconhecido'}. Aguardando QR Code...`);
      }
      setIsLoading(false);

      if (pollingIntervalRef.current) {
         clearInterval(pollingIntervalRef.current);
      }
      pollingIntervalRef.current = setInterval(checkStatus, 3000);

    } catch (err) {
      const errorText = err.response?.data?.detail || err.response?.data || err.message;
      let friendlyError = errorText;
      let isAlreadyConnected = false;

      try {
        let errorObj;
        if (typeof errorText === 'string') {
            errorObj = JSON.parse(errorText);
        } else if (typeof errorText === 'object') {
            errorObj = errorText;
        }

        if (errorObj && (errorObj.status === 'CONNECTED' || errorObj.status === 'open')) {
            friendlyError = "A instância já está conectada. Redirecionando...";
            isAlreadyConnected = true;
        }
        if (errorObj && errorObj.response && errorObj.response.message) {
            friendlyError = errorObj.response.message[0];
        }

      } catch(e) { /* Não era JSON */ }

      if (isAlreadyConnected) {
        console.log("Erro 'CONNECTED/OPEN' detectado. Forçando verificação de status...");
        setStatusMessage(friendlyError);
        checkStatus();
      } else {
        setError(`Erro ao buscar QR Code: ${friendlyError}`);
      }

      setIsLoading(false);
      console.error(err);
    }
  }, [checkStatus]); // Depende de checkStatus (que agora é estável)


  // --- EFEITO PRINCIPAL (Lógica Corrigida) ---
  useEffect(() => {
    const initializeConnection = async () => {
        console.log("Verificando status inicial...");
        setIsLoading(true);
        const isConnected = await checkStatus();

        if (!isConnected) {
            console.log("Não conectado. Buscando QR code...");
            await fetchQRCode();
        }
        setIsLoading(false);
    };
    initializeConnection();
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  // --- 💡 CORREÇÃO 4/4: Dependências corretas do useEffect ---
  }, [checkStatus, fetchQRCode]);


  const handleReload = () => {
      window.location.reload();
  };

  // --- JSX (HTML) ---
  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      <h2>Conecte seu WhatsApp</h2>
      {error && <div style={{ color: 'red', margin: '10px' }}>{error}</div>}
      <div className="qr-code-wrapper" style={{ margin: '30px', minHeight: '256px' }}>
        {(isLoading || (!error && !qrImageSrc)) && (
            <p>{statusMessage}</p>
        )}
        {qrImageSrc && !error && (
          <img
            src={qrImageSrc}
            alt="Escaneie este QR Code"
            style={{ width: 256, height: 256, border: '1px solid #ccc' }}
          />
        )}
      </div>
      <p style={{fontSize: '0.8em', color: '#666'}}>
        {instanceName ? `Instância: ${instanceName}` : ''}
      </p>
      <button onClick={handleReload} disabled={isLoading}>
        {isLoading ? 'Aguarde...' : 'Recarregar'}
      </button>
    </div>
  );
}

export default ConnectInstancePage;