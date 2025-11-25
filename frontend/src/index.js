
import React from 'react';
import ReactDOM from 'react-dom/client';

import './styles/global.css';
import './styles/animations.css';
import './styles/loading.css';
import './styles/layout.css';
import './styles/auth.css';
import './styles/sidebar.css';
import './styles/chat.css';
import './styles/copilot.css';
import './styles/components.css';

import App from './App';


import { AuthProvider } from './hooks/useAuth';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </React.StrictMode>
);