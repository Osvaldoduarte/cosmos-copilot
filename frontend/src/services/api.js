// frontend/src/services/api.js
import axios from 'axios';

const api = axios.create({
    //baseURL: 'https://cosmos-backend-129644477821.us-central1.run.app' // URL do seu backend
    baseURL: 'http://127.0.0.1:8000'
});

// Interceptor: Anexa o token JWT em CADA requisição
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;