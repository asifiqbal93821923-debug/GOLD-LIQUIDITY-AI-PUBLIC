import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './style.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const workerUrl = new URL('sw.js', import.meta.env.BASE_URL).toString();
    navigator.serviceWorker.register(workerUrl).catch(error => {
      console.warn('Offline shell registration failed:', error);
    });
  });
}
