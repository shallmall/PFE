import React from 'react';
import { ShieldCheck, Search, UploadCloud, Database, Radio } from 'lucide-react';

export default function Header({ searchQuery, setSearchQuery, onOpenPortal, onOpenReviewerDemo, useLiveApi, setUseLiveApi }) {
  return (
    <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-xs transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        
        {/* Left Logo */}
        <div className="flex items-center gap-2 cursor-pointer select-none">
          <div className="bg-gradient-to-tr from-indigo-600 to-violet-600 text-white p-2 rounded-xl shadow-md shadow-indigo-500/20">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xl font-black tracking-tight text-slate-900">Verified</span>
            <span className="text-xl font-bold tracking-tight text-indigo-600">Store</span>
          </div>
          <span className="hidden sm:inline-block ml-2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-indigo-50 text-indigo-700 rounded-full border border-indigo-200">
            AI Ledger Protected
          </span>
        </div>

        {/* Center Search Input */}
        <div className="flex-1 max-w-md mx-auto relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search products by name or ASIN..."
            className="w-full pl-9 pr-4 py-2 bg-slate-100/80 hover:bg-slate-100 focus:bg-white text-sm text-slate-900 rounded-xl border border-transparent focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all outline-none"
          />
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2.5">
          {/* Demo Reviewer Button */}
          <button
            onClick={() => onOpenReviewerDemo({ id: "usr_genuine_001", name: "Alice Smith" })}
            className="flex items-center gap-1.5 px-3 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-xl border border-indigo-200 shadow-2xs transition-all cursor-pointer"
          >
            <span>👤 Reviewer Showcase</span>
          </button>

          {/* Live API vs Mock Mode Toggle */}
          <button
            onClick={() => setUseLiveApi(!useLiveApi)}
            title={useLiveApi ? "Connected to Local FastAPI AI Engine" : "Running on Static Mock Data"}
            className={`hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              useLiveApi
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 shadow-xs"
                : "bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200"
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${useLiveApi ? "animate-pulse text-emerald-500" : "text-slate-400"}`} />
            {useLiveApi ? "Live AI Engine Mode" : "Static Catalog Mode"}
          </button>

          {/* Submitter Portal Button */}
          <button
            onClick={onOpenPortal}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-900 hover:bg-indigo-600 text-white text-xs font-medium rounded-xl shadow-sm hover:shadow-md hover:shadow-indigo-500/20 transition-all active:scale-95 cursor-pointer"
          >
            <UploadCloud className="w-4 h-4 text-indigo-300" />
            <span className="hidden sm:inline">Submitter Portal</span>
          </button>
        </div>

      </div>
    </header>
  );
}
