import React, { useState, useEffect } from 'react';
import { Star, ShieldAlert, ShieldCheck, MessageSquare, AlertTriangle, ChevronRight, Building2, Layers, Filter } from 'lucide-react';

export default function ProductCatalog({ searchQuery, onSelectProduct }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProducts = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/v1/products');
        if (!res.ok) throw new Error("Failed to load products from API gateway");
        const data = await res.json();
        setProducts(data);
      } catch (err) {
        console.error("Fetch error:", err);
        setError("Could not load products. Make sure the backend API server is running on port 8000.");
      } finally {
        setLoading(false);
      }
    };
    fetchProducts();
  }, []);

  // Filter by search query (name, ID, category, or submitter ID)
  const filteredProducts = products.filter(p => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      (p.name && p.name.toLowerCase().includes(q)) ||
      (p.product_id && p.product_id.toLowerCase().includes(q)) ||
      (p.category && p.category.toLowerCase().includes(q)) ||
      (p.submitter_id && p.submitter_id.toLowerCase().includes(q))
    );
  });

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium animate-pulse">Loading Alastria Verified Product Catalog...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-20 p-8 glass-card rounded-3xl border-rose-500/40 text-center">
        <AlertTriangle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
        <h3 className="text-xl font-bold text-white mb-2">Connection Error</h3>
        <p className="text-slate-300 text-sm mb-6">{error}</p>
        <button 
          onClick={() => window.location.reload()}
          className="px-6 py-2.5 bg-rose-500 hover:bg-rose-600 text-white font-medium rounded-xl transition-all"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fadeIn">
      
      {/* Hero Banner */}
      <div className="mb-10 p-8 rounded-3xl bg-gradient-to-r from-slate-900/90 via-slate-900/50 to-slate-900/90 border border-slate-800 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-3xl relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold uppercase tracking-wider mb-4">
            <Layers className="w-3.5 h-3.5" />
            <span>Phase 7: Public Verifier Explorer</span>
          </div>
          <h2 className="text-4xl font-extrabold text-white tracking-tight leading-tight">
            Decentralized Product Reputation Catalog
          </h2>
          <p className="text-slate-400 mt-3 text-base leading-relaxed">
            Explore products monitored by our Late Fusion AI Engine (GNN + DeBERTa) and anchored on Spain's national Alastria Red T blockchain. Compare raw customer star ratings against deep AI fraud risk scores.
          </p>
        </div>
      </div>

      {/* Catalog Grid Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <h3 className="text-xl font-bold text-white">Monitored Products</h3>
          <span className="bg-slate-800 text-slate-300 text-xs font-bold px-2.5 py-1 rounded-full border border-slate-700">
            {filteredProducts.length}
          </span>
        </div>
        {searchQuery && (
          <p className="text-sm text-cyan-400 font-medium">
            Filtering by: "{searchQuery}"
          </p>
        )}
      </div>

      {/* Product Grid */}
      {filteredProducts.length === 0 ? (
        <div className="text-center py-20 glass-card rounded-3xl">
          <p className="text-slate-400 text-lg">No products found matching "{searchQuery}"</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredProducts.map((prod) => {
            const riskScore = Math.round((prod.avg_ai_score || 0) * 100);
            let riskLabel = "Inconclusive / Gray Area";
            let riskColor = "text-amber-400";
            let barGradient = "bg-gradient-to-r from-amber-500 to-yellow-400 shadow-sm shadow-amber-500/50";
            let cornerGlow = "bg-amber-500/10 group-hover:bg-amber-500/20";
            
            if (riskScore < 30) {
              riskLabel = "Verified Authentic";
              riskColor = "text-emerald-400";
              barGradient = "bg-gradient-to-r from-teal-500 to-emerald-400 shadow-sm shadow-emerald-500/50";
              cornerGlow = "bg-emerald-500/10 group-hover:bg-emerald-500/20";
            } else if (riskScore > 80) {
              riskLabel = "High Fraud Probability";
              riskColor = "text-rose-400";
              barGradient = "bg-gradient-to-r from-amber-500 to-rose-500 shadow-sm shadow-rose-500/50";
              cornerGlow = "bg-rose-500/10 group-hover:bg-rose-500/20";
            }
            
            return (
              <div
                key={prod.universal_product_id}
                onClick={() => onSelectProduct(prod)}
                className="glass-card rounded-3xl p-6 cursor-pointer flex flex-col justify-between group relative overflow-hidden"
              >
                {/* Top Corner Glow */}
                <div className={`absolute top-0 right-0 w-32 h-32 rounded-full blur-2xl pointer-events-none transition-all ${cornerGlow}`} />

                <div>
                  {/* Submitter Pill & Category */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-slate-300 text-xs font-mono font-medium">
                      <Building2 className="w-3 h-3 text-cyan-400" />
                      <span>{prod.submitter_id || "AMAZON_US"}</span>
                    </span>
                    {prod.category && (
                      <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
                        {prod.category}
                      </span>
                    )}
                  </div>

                  {/* Product Name & ID */}
                  <h4 className="text-lg font-bold text-white group-hover:text-cyan-300 transition-colors line-clamp-1">
                    {prod.name || `Product ${prod.product_id}`}
                  </h4>
                  <p className="text-xs text-slate-500 font-mono mt-0.5 mb-5">
                    ID: {prod.product_id}
                  </p>

                  {/* Star Rating vs AI Risk Thermometer (Showcase Feature) */}
                  <div className="bg-slate-900/70 border border-slate-800/80 rounded-2xl p-4 mb-5 space-y-3">
                    
                    {/* Star Rating */}
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-1.5 text-amber-400 font-bold">
                        <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                        <span>{prod.avg_rating.toFixed(1)} <span className="text-xs font-normal text-slate-400">/ 5.0</span></span>
                      </div>
                      <span className="text-xs text-slate-400">Raw Customer Rating</span>
                    </div>

                    {/* Risk Thermometer Bar */}
                    <div>
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="text-slate-400 font-medium">AI Fraud Ring Risk:</span>
                        <span className={`font-bold ${riskColor}`}>
                          {riskScore}% — {riskLabel}
                        </span>
                      </div>
                      <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden p-0.5">
                        <div 
                          className={`h-full rounded-full transition-all duration-500 ${barGradient}`}
                          style={{ width: `${Math.max(8, riskScore)}%` }}
                        />
                      </div>
                    </div>

                  </div>
                </div>

                {/* Footer Stats & Arrow */}
                <div className="flex items-center justify-between pt-4 border-t border-slate-800/80 text-xs">
                  <div className="flex items-center gap-3 text-slate-400">
                    <div className="flex items-center gap-1">
                      <MessageSquare className="w-3.5 h-3.5 text-slate-500" />
                      <span><strong>{prod.review_count}</strong> reviews</span>
                    </div>
                    {prod.fraud_count > 0 && (
                      <div className="flex items-center gap-1 text-rose-400 font-medium">
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span><strong>{prod.fraud_count}</strong> fake</span>
                      </div>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-1 text-cyan-400 font-semibold group-hover:translate-x-1 transition-transform">
                    <span>Inspect</span>
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
