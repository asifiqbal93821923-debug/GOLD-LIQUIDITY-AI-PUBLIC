import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './style.css';

class AppErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('Dashboard render failed:', error, info); }
  render() {
    if (this.state.error) return <main style={{minHeight:'100vh',background:'#090d14',color:'#e8eef7',fontFamily:'system-ui',padding:'28px 18px'}}>
      <h2 style={{color:'#e7bd79'}}>Gold Terminal could not start</h2>
      <p style={{color:'#9aa8b9'}}>অ্যাপ চালু করতে একটি JavaScript সমস্যা হয়েছে। নিচের error তথ্যটি support/debugging-এর জন্য:</p>
      <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',background:'#151e2b',padding:14,borderRadius:10,color:'#ffadb4'}}>{String(this.state.error?.message||this.state.error)}</pre>
      <button onClick={()=>window.location.reload()} style={{padding:'10px 16px',borderRadius:8,border:0,background:'#c49a5c',color:'#10151d'}}>Reload app</button>
    </main>;
    return this.props.children;
  }
}
createRoot(document.getElementById('root')).render(<React.StrictMode><AppErrorBoundary><App /></AppErrorBoundary></React.StrictMode>);
// Disable the old offline worker while the dashboard stabilizes.
// Remove stale shell caches left by previous releases; always load the current
// hashed Vite assets from the network on GitHub Pages.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations()
    .then(registrations => Promise.all(registrations.map(registration => registration.unregister())))
    .catch(error => console.warn('Service worker cleanup:', error));
}
if ('caches' in window) {
  caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith('gold-terminal-')).map(key => caches.delete(key))))
    .catch(error => console.warn('Old app cache cleanup:', error));
}
