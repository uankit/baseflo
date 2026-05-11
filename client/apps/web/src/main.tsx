import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/base.css';
import { App } from './App.js';

const rootEl = document.getElementById('root');
if (!rootEl) {
  throw new Error("#root element missing — check apps/web/index.html.");
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
