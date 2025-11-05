// Em frontend/src/index.js
// (SUBSTITUA o conteúdo deste arquivo)

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// 💡 CORREÇÃO: Importa o AuthProvider do local correto.
// (Assumindo que seu 'useAuth.js' também exporta o Provider)
// Se você o moveu para 'context/AuthContext.js', mude o caminho.
import { AuthProvider } from './hooks/useAuth';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    {/* O AuthProvider DEVE envolver o App */}
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
);