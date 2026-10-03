import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { PreferenciasProvider } from './context/PreferenciasContext'
import { ToastProvider } from './components/ui/Toast'

// Rediseño (Etapa 0): tema y pausa de animaciones (PreferenciasProvider) y la
// región única de avisos emergentes (ToastProvider), por encima de todo.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PreferenciasProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </PreferenciasProvider>
  </React.StrictMode>,
)
