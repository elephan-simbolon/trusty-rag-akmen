import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

if (!localStorage.getItem('theme')) localStorage.setItem('theme', 'dark');

if (import.meta.env.DEV && !import.meta.env.VITE_API_BASE_URL) {
  console.error('VITE_API_BASE_URL is not set. Copy .env.local.example to .env.local and configure it.');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
