import React from 'react';
import { X, ShieldCheck, UserCheck, UserX, Star, ShieldAlert, Cpu, Hash, KeyRound } from 'lucide-react';

export default function ProductDetailModal({ product, onClose, onSelectReviewer }) {
  if (!product) return null;

  const reviews = product.reviews || [];

  const normScore = (v) => {
    if (v === undefined || v === null || isNaN(v)) return 50;
    let n = Number(v);
    if (n > 100) n = Math.round((n / 255) * 100);
    return Math.max(0, Math.min(100, Math.round(n)));
  };

  const prodScore = normScore(product.product_score ?? 50);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="p-6 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            {product.image && (
              <img src={product.image} alt={product.product_name} className="w-16 h-16 rounded-2xl object-cover border-2 border-white/20" />
            )}
            <div>
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-indigo-500/30 text-indigo-200 border border-indigo-400/30 mb-1 inline-block">
                {product.category || "Verified Product"}
              </span>
              <h2 className="text-xl font-bold leading-tight">{product.product_name}</h2>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-300 font-mono">
                <span>ASIN: {product.product_id}</span>
                <span>•</span>
                <span>Submitter: {product.submitter_id}</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-white/10 text-slate-300 hover:text-white transition-colors cursor-pointer"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Product Overall Reputation Banner */}
        <div className="bg-indigo-50/60 border-b border-indigo-100 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-600 text-white p-2.5 rounded-2xl shadow-sm">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Late Fusion AI & Blockchain Evaluation</h4>
              <p className="text-xs text-slate-600">
                Aggregated from {reviews.length} cryptographically anchored customer evaluations.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-white px-4 py-2 rounded-2xl border border-indigo-200 shadow-2xs">
            <span className="text-xs font-bold text-slate-500 uppercase">Reviewee Score</span>
            <span className="font-mono text-2xl font-black text-indigo-600">{prodScore}</span>
            <span className="text-xs font-semibold text-slate-400">/ 100</span>
          </div>
        </div>

        {/* Reviews List */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          <h3 className="text-base font-bold text-slate-800 mb-2 flex items-center gap-2">
            <span>Customer Reviews & AI Authenticity Analysis</span>
            <span className="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-mono">
              {reviews.length}
            </span>
          </h3>

          {reviews.length === 0 ? (
            <div className="text-center py-12 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
              <p className="text-slate-500 text-sm">No reviews evaluated for this product yet.</p>
            </div>
          ) : (
            reviews.map((rev, idx) => {
              const revScore = normScore(rev.reviewer_score ?? rev.ai_score ?? 50);
              const isTrusted = revScore >= 55;

              return (
                <div
                  key={rev.universal_review_id || idx}
                  className={`p-5 rounded-2xl border transition-all ${
                    isTrusted
                      ? "bg-white border-slate-200 hover:border-emerald-300"
                      : "bg-rose-50/40 border-rose-200/80 hover:border-rose-300"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                    {/* Reviewer Info */}
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm ${
                        isTrusted ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                      }`}>
                        {isTrusted ? <UserCheck className="w-5 h-5" /> : <UserX className="w-5 h-5" />}
                      </div>
                      <div>
                        <div
                          onClick={() => onSelectReviewer && onSelectReviewer({ id: rev.reviewer_id, name: rev.reviewer_name })}
                          className="flex flex-wrap items-center gap-2 cursor-pointer group/rev"
                        >
                          <span className="font-bold text-slate-900 text-sm group-hover/rev:text-indigo-600 underline-offset-2 group-hover/rev:underline transition-all">
                            {rev.reviewer_name || "Anonymous User"}
                          </span>
                          <span className="text-xs font-mono text-slate-400">({rev.reviewer_id})</span>
                          <span className={`px-2 py-0.5 rounded-md text-[11px] font-bold border ${
                            isTrusted
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                              : "bg-rose-50 text-rose-700 border-rose-200"
                          }`}>
                            Reviewer Score: {revScore}/100 ↗
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-amber-500 mt-0.5">
                          {[...Array(5)].map((_, i) => (
                            <Star
                              key={i}
                              className={`w-3.5 h-3.5 ${
                                i < Math.floor(rev.review_rating || 5) ? "fill-amber-400" : "text-slate-200"
                              }`}
                            />
                          ))}
                          <span className="text-xs font-bold text-slate-700 ml-1">{rev.review_rating || 5.0}</span>
                        </div>
                      </div>
                    </div>

                    {/* Reviewer Reputation Badge */}
                    <div className="flex items-center gap-2">
                      <div className={`px-3 py-1 rounded-xl text-xs font-bold flex items-center gap-1.5 border ${
                        isTrusted
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                          : "bg-rose-100 text-rose-800 border-rose-300"
                      }`}>
                        {isTrusted ? (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5" />
                            <span>Reviewer Trust: {revScore}/100</span>
                          </>
                        ) : (
                          <>
                            <ShieldAlert className="w-3.5 h-3.5 animate-pulse" />
                            <span>Spam Risk: {revScore}/100</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Review Body */}
                  <p className="text-slate-700 text-sm leading-relaxed mb-3 font-normal">
                    "{rev.review_text}"
                  </p>

                  {/* Blockchain Footer & All 3 IDs */}
                  <div className="pt-3 border-t border-slate-100/80 flex flex-col gap-2 text-[11px] text-slate-400 font-mono">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 overflow-hidden text-ellipsis">
                        <Hash className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                        <span className="text-slate-500 font-semibold">Alastria Hash:</span>
                        <code className="bg-slate-100 px-1.5 py-0.5 rounded text-indigo-600 font-semibold truncate max-w-[220px]">
                          {rev.tx_hash || "0xAnchoredStorageSlot"}
                        </code>
                      </div>
                      <span>{rev.created_at || "Recent Evaluation"}</span>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2 pt-1.5 border-t border-slate-100/60 text-[10px]">
                      <div className="flex items-center gap-1">
                        <span className="text-slate-400 font-semibold">1. Review ID:</span>
                        <code className="bg-slate-100 text-slate-700 font-bold px-1.5 py-0.5 rounded">{rev.universal_review_id || "0x0"}</code>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-slate-400 font-semibold">2. Reviewer ID:</span>
                        <code className="bg-indigo-50 text-indigo-700 font-bold px-1.5 py-0.5 rounded border border-indigo-200">{rev.reviewer_id || "usr_01"}</code>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-slate-400 font-semibold">3. Reviewee ID:</span>
                        <code className="bg-emerald-50 text-emerald-700 font-bold px-1.5 py-0.5 rounded border border-emerald-200">{product.product_id || rev.reviewee_id || "ASIN_01"}</code>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span>Protected by Alastria Red T Smart Contract <code>0x729F0008...</code></span>
          <button
            onClick={onClose}
            className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-xl transition-all cursor-pointer"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
