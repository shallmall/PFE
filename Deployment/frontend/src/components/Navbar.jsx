import React, { useState, useEffect } from 'react';
import { Shield, Search, Upload, RefreshCw, CheckCircle2, Clock, Activity, Home, BarChart3 } from 'lucide-react';

export default function Navbar({ 
  currentView, 
  setCurrentView, 
  searchQuery, 
  setSearchQuery, 
  onOpenSubmitModal,
  hasDashboardReport 
}) {
  const [ledgerStatus, setLedgerStatus] = useState({
    confirmed_onchain_count: 0,
    pending_ledger_count: 0,
    status_message: "Checking Alastria Red T..."
  });
  const [syncing, setSyncing] = useState(false);

  const fetchLedgerStatus = async () => {
    try {
      const res = await fetch('/api/v1/ledger/status');
      if (res.ok) {
        const data = await res.json();
        setLedgerStatus(data);
      }
    } catch (err) {
      console.error("Failed to fetch ledger status:", err);
    }
  };

  useEffect(() => {
    fetchLedgerStatus();
    const interval = setInterval(fetchLedgerStatus, 6000);
    return () => clearInterval(interval);
  }, []);

  const handleManualSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch('/api/v1/ledger/sync', { method: 'POST' });
      if (res.ok) {
        await fetchLedgerStatus();
      }
    } catch (err) {
      console.error("Sync failed:", err);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <nav className="glass-nav sticky top-0 z-50 px-6 py-4 transition-all">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Brand Logo & Title */}
        <div 
          onClick={() => setCurrentView('catalog')} 
          className="flex items-center gap-3 cursor-pointer group"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
            <Shield className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-white via-cyan-200 to-cyan-400 bg-clip-text text-transparent tracking-tight">
              Alastria Red T
            </h1>
            <p className="text-xs text-cyan-400/80 font-medium tracking-wide">
              DECENTRALIZED REPUTATION LEDGER
            </p>
          </div>
        </div>

        {/* Live Search Bar */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search products, reviewers, IDs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900/60 border border-slate-700/60 rounded-full text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:border-cyan-500/60 focus:ring-2 focus:ring-cyan-500/20 transition-all shadow-inner"
          />
          {searchQuery && (
            <button 
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-white bg-slate-800 px-1.5 py-0.5 rounded-full"
            >
              ✕
            </button>
          )}
        </div>

        {/* Live Alastria Web3 Sync Ticker & Controls */}
        <div className="flex items-center gap-3 w-full md:w-auto justify-end flex-wrap">
          
          {/* Ticker Badges */}
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-700/50 rounded-full px-3 py-1.5 text-xs shadow-sm">
            <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>On-Chain: <strong className="text-white font-bold">{ledgerStatus.confirmed_onchain_count}</strong></span>
            </div>
            <span className="text-slate-600">|</span>
            <div className="flex items-center gap-1.5 text-amber-400 font-medium">
              <Clock className="w-3.5 h-3.5" />
              <span>Queue: <strong className="text-white font-bold">{ledgerStatus.pending_ledger_count}</strong></span>
            </div>
          </div>

          {/* Sweep Button */}
          <button
            onClick={handleManualSync}
            disabled={syncing}
            title="Trigger manual zero-gas sweep to Alastria blockchain"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/30 rounded-full text-xs font-medium transition-all hover:border-cyan-400 disabled:opacity-50 active:scale-95 shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-cyan-400' : ''}`} />
            <span>{syncing ? 'Sweeping...' : 'Sweep to Chain'}</span>
          </button>

          {/* Nav Buttons */}
          <button
            onClick={() => setCurrentView('catalog')}
            className={`p-2 rounded-xl transition-all ${
              currentView === 'catalog' ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
            title="Product Catalog"
          >
            <Home className="w-5 h-5" />
          </button>

          {hasDashboardReport && (
            <button
              onClick={() => setCurrentView('dashboard')}
              className={`p-2 rounded-xl transition-all ${
                currentView === 'dashboard' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/40' : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
              title="Submitter Report Dashboard"
            >
              <BarChart3 className="w-5 h-5" />
            </button>
          )}

          {/* Submit Batch Button */}
          <button
            onClick={onOpenSubmitModal}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-medium text-sm rounded-xl shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 active:scale-95"
          >
            <Upload className="w-4 h-4" />
            <span>Submit Batch</span>
          </button>

        </div>
      </div>
    </nav>
  );
}
