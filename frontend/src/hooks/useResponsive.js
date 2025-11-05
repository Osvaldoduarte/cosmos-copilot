import { useState, useEffect } from 'react';

// Um hook simples para gerenciar o estado de responsividade
export function useResponsive() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);

    // Limpeza do listener
    return () => window.removeEventListener('resize', handleResize);
  }, []); // Array vazio garante que rode apenas na montagem/desmontagem

  return isMobile;
}