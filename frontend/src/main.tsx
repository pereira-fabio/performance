import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import 'leaflet/dist/leaflet.css';
import './index.css';
import { getTheme, applyTheme } from './lib/theme';

applyTheme(getTheme());

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
