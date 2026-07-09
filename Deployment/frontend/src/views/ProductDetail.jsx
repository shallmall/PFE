import React, { useState, useEffect } from 'react';
import { ArrowLeft, Star, ShieldAlert, ShieldCheck, User, Building2, Hash, ExternalLink, Calendar, CheckCircle2, Award, Terminal, Copy } from 'lucide-react';

export default function ProductDetail({ product, onBack, onSelectReviewer }) {
  const [reviews, setReviews] = useState([]);
  const [reviewerMap, setReviewerMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedTx, setSelectedTx] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // Fetch product reviews and all reviewers simultaneously to map reputation scores
        const targetId = product.universal_product_id || product.product_id;
        const [revRes, usersRes] = await Promise.all([
          fetch(`/api/v1/reviews/product/${targetId}`),
          fetch(`/api/v1/reviewers`)
        ]);

        if (revRes.ok) {
          const revData = await revRes.json();
          setReviews(revData);
        }
        if (usersRes.ok) {
          const usersData = await usersRes.json();
          const map = {};
          usersData.forEach(u => {
            map[u.reviewer_id] = u;
            map[u.universal_reviewer_id] = u;
          });
          setReviewerMap(map);
        }
      } catch (err) {
        console.error("Failed to load product reviews:", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [product.product_id, product.universal_product_id]);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fadeIn">
      
      {/* Back Button */}
      <button 
        onClick={onBack}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-sm font-medium mb-8 transition-all hover:-translate-x-1"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Product Catalog</span>
      </button>

      {/* Product Header Card */}
      <div className="glass-card rounded-3xl p-8 mb-10 relative overflow-hidden border-cyan-500/30">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono font-medium">
                <Building2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>Submitter: {product.submitter_id || "AMAZON_US"}</span>
              </span>
              {product.category && (
                <span className="px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
                  {product.category}
                </span>
              )}
            </div>
            <h2 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight">
              {product.name || `Product ${product.product_id}`}
            </h2>
            <div className="flex items-center gap-2 mt-1 font-mono text-sm">
              <span className="text-slate-400">Universal Keccak ID:</span>
              <strong className="text-slate-200 select-all">{product.universal_product_id}</strong>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(product.universal_product_id);
                }}
                title="Copy full Universal Keccak ID"
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-cyan-400 transition-colors text-xs"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </button>
            </div>
          </div>

          {/* Stats Badges */}
          <div className="flex items-center gap-4 bg-slate-900/80 border border-slate-800 p-4 rounded-2xl">
            <div className="text-center px-4 border-r border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Customer Rating</span>
              <div className="flex items-center justify-center gap-1 text-amber-400 font-extrabold text-2xl">
                <Star className="w-5 h-5 fill-amber-400" />
                <span>{product.avg_rating.toFixed(1)}</span>
              </div>
            </div>
            <div className="text-center px-4">
              <span className="text-xs text-slate-400 block mb-1">Total Reviews</span>
              <span className="font-extrabold text-2xl text-white">
                {product.review_count}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Reviews Section Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-2xl font-bold text-white">Decentralized Review Audit Log</h3>
          <p className="text-sm text-slate-400 mt-0.5">
            Every review is scored by Late Fusion AI and cryptographically anchored to Alastria Red T.
          </p>
        </div>
        <span className="bg-slate-800 text-slate-300 text-xs font-bold px-3 py-1 rounded-full border border-slate-700">
          {reviews.length} Verified Records
        </span>
      </div>

      {/* Reviews List */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <div className="w-10 h-10 border-4 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin" />
          <p className="text-slate-400 font-medium">Fetching verified on-chain review records...</p>
        </div>
      ) : reviews.length === 0 ? (
        <div className="text-center py-16 glass-card rounded-3xl">
          <p className="text-slate-400">No reviews found for this product in the ledger.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((rev) => {
            const revScore = Math.round((rev.ai_score || 0) * 100);
            let riskLabel = "Inconclusive / Gray Area";
            let badgeBg = "bg-amber-500/10 border-amber-500/40 text-amber-300";
            let iconColor = "text-amber-400";
            let borderStyle = "border-l-amber-500 bg-amber-950/10";
            
            if (revScore < 30) {
              riskLabel = "Verified Authentic";
              badgeBg = "bg-emerald-500/10 border-emerald-500/40 text-emerald-300";
              iconColor = "text-emerald-400";
              borderStyle = "border-l-emerald-500 bg-emerald-950/10";
            } else if (revScore > 80) {
              riskLabel = "High Fraud Probability";
              badgeBg = "bg-rose-500/10 border-rose-500/40 text-rose-300";
              iconColor = "text-rose-400";
              borderStyle = "border-l-rose-500 bg-rose-950/10";
            }

            const reviewerInfo = reviewerMap[rev.reviewer_id] || reviewerMap[rev.universal_reviewer_id] || {};
            const authorRep = reviewerInfo.current_score !== undefined 
              ? Math.round(reviewerInfo.current_score * 100) 
              : Math.round(max(0, 100 - revScore));

            return (
              <div 
                key={rev.universal_review_id}
                className={`glass-card rounded-3xl p-6 transition-all border-l-4 ${borderStyle}`}
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  
                  {/* Review Main Content */}
                  <div className="flex-1 space-y-3">
                    
                    {/* Top Row: Reviewer & Rating */}
                    <div className="flex items-center flex-wrap gap-3">
                      
                      {/* Reviewer Profile Link */}
                      <button
                        onClick={() => onSelectReviewer(rev.reviewer_id || reviewerInfo.universal_reviewer_id)}
                        className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 border border-slate-600/80 text-white text-xs font-semibold transition-all group"
                      >
                        <User className="w-3.5 h-3.5 text-cyan-400" />
                        <span className="group-hover:text-cyan-300 underline decoration-cyan-500/50">
                          {rev.reviewer_name || reviewerInfo.name || (rev.reviewer_id.startsWith("0x") ? `${rev.reviewer_id.slice(0, 14)}...` : rev.reviewer_id)}
                        </span>
                        <span className="bg-slate-900 px-1.5 py-0.5 rounded text-[10px] text-cyan-400 font-mono">
                          Rep: {authorRep}/100
                        </span>
                      </button>

                      {/* Star Rating */}
                      <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded-full border border-slate-800 text-xs font-bold text-amber-400">
                        <Star className="w-3.5 h-3.5 fill-amber-400" />
                        <span>{rev.rating ? rev.rating.toFixed(1) : "5.0"}</span>
                      </div>

                      {/* Date */}
                      {rev.review_date && (
                        <div className="flex items-center gap-1 text-xs text-slate-400">
                          <Calendar className="w-3.5 h-3.5" />
                          <span>{new Date(rev.review_date).toLocaleDateString()}</span>
                        </div>
                      )}

                      {/* Submitter Badge */}
                      <span className="text-[11px] text-slate-500 font-mono">
                        via {rev.submitter_id || product.submitter_id || "AMAZON_US"}
                      </span>
                    </div>

                    {/* Review Text */}
                    <p className="text-slate-200 text-sm md:text-base leading-relaxed font-normal">
                      "{rev.review_text || "No written review content provided."}"
                    </p>

                    {/* Cryptographic Badges Row */}
                    <div className="flex items-center flex-wrap gap-2 pt-2">
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-slate-800 text-[11px] font-mono text-slate-300">
                        <Hash className="w-3 h-3 text-slate-500 flex-shrink-0" />
                        <span className="text-slate-500">ID:</span>
                        <span className="select-all text-slate-200 font-semibold">{rev.universal_review_id}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard.writeText(rev.universal_review_id);
                          }}
                          title="Copy full Universal Keccak ID"
                          className="ml-1 p-0.5 hover:bg-slate-800 rounded text-slate-400 hover:text-cyan-400 transition-colors"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {/* Web3 Receipt Hash Badge */}
                      {rev.tx_hash ? (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-[11px] font-mono text-cyan-300 shadow-sm">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                          <button
                            onClick={() => setSelectedTx(rev)}
                            className="hover:underline flex items-center gap-1 text-left"
                            title="Inspect Alastria Audit Receipt"
                          >
                            <span>Alastria Red T Tx: {rev.tx_hash}</span>
                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigator.clipboard.writeText(rev.tx_hash);
                            }}
                            title="Copy full Tx Hash"
                            className="ml-1 p-0.5 hover:bg-cyan-900 rounded text-cyan-400 hover:text-white transition-colors"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-950/40 border border-amber-800/50 text-[11px] font-mono text-amber-400">
                          <span>Pending Alastria Anchor</span>
                        </span>
                      )}
                    </div>

                  </div>

                  {/* AI Score Badge Card */}
                  <div className={`p-4 rounded-2xl border text-center min-w-[150px] flex-shrink-0 ${badgeBg}`}>
                    <div className="flex items-center justify-center gap-1.5 mb-1 font-bold text-xs">
                      {revScore > 80 ? <ShieldAlert className={`w-4 h-4 ${iconColor}`} /> : <ShieldCheck className={`w-4 h-4 ${iconColor}`} />}
                      <span>{riskLabel}</span>
                    </div>
                    <div className="text-2xl font-extrabold font-mono">
                      {revScore}%
                    </div>
                    <span className="text-[10px] text-slate-400 block mt-0.5 uppercase tracking-wider">
                      AI Fraud Risk
                    </span>
                  </div>

                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Cryptographic Inspection Drawer / Modal (Showcase Feature) */}
      {selectedTx && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
          <div className="glass-modal w-full max-w-xl rounded-3xl p-8 relative border border-cyan-500/40 shadow-2xl">
            <button 
              onClick={() => setSelectedTx(null)}
              className="absolute top-6 right-6 text-slate-400 hover:text-white bg-slate-800 p-2 rounded-full"
            >
              ✕
            </button>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center">
                <Terminal className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Alastria Red T Audit Receipt</h3>
                <p className="text-xs text-cyan-400">100% Immutable Trustless Verification</p>
              </div>
            </div>

            <div className="space-y-4 bg-slate-950/80 p-5 rounded-2xl font-mono text-xs text-slate-300 border border-slate-800">
              <div>
                <span className="text-slate-500 block mb-1">Smart Contract Tx Hash:</span>
                <span className="text-cyan-400 break-all font-bold bg-cyan-950/40 p-2 rounded block border border-cyan-900">
                  {selectedTx.tx_hash}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block mb-1">Universal Review Keccak ID:</span>
                <span className="text-slate-200 break-all bg-slate-900 p-2 rounded block">
                  {selectedTx.universal_review_id}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800 text-[11px]">
                <div>
                  <span className="text-slate-500 block">Consortium Network:</span>
                  <span className="text-emerald-400 font-bold">Alastria Red T (EVM 0.8.19)</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Storage Slot Optimization:</span>
                  <span className="text-purple-400 font-bold">1-Slot Packed (6 Bytes)</span>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedTx(null)}
                className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-sm font-medium transition-all"
              >
                Close Receipt
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
