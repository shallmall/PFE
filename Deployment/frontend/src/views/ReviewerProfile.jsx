import React, { useState, useEffect } from 'react';
import { ArrowLeft, User, ShieldAlert, ShieldCheck, Star, Building2, Hash, CheckCircle2, ExternalLink, Calendar, Award, AlertTriangle, Copy } from 'lucide-react';

export default function ReviewerProfile({ reviewerId, onBack }) {
  const [reviewer, setReviewer] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadReviewerData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch reviewer summary and all their reviews simultaneously
        const [revsRes, myReviewsRes] = await Promise.all([
          fetch('/api/v1/reviewers'),
          fetch(`/api/v1/reviews/reviewer/${encodeURIComponent(reviewerId)}`)
        ]);

        if (revsRes.ok) {
          const allReviewers = await revsRes.json();
          const found = allReviewers.find(r => r.reviewer_id === reviewerId || r.universal_reviewer_id === reviewerId);
          if (found) setReviewer(found);
        }

        if (myReviewsRes.ok) {
          const myRevs = await myReviewsRes.json();
          setReviews(myRevs);
        } else {
          throw new Error("Could not fetch reviewer audit logs");
        }
      } catch (err) {
        console.error("Profile load error:", err);
        setError("Failed to load reviewer profile and historical reviews.");
      } finally {
        setLoading(false);
      }
    };
    loadReviewerData();
  }, [reviewerId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium">Verifying Reviewer Trust on Alastria Red T...</p>
      </div>
    );
  }

  const repScore = reviewer ? Math.round((reviewer.current_score || 0) * 100) : 50;
  let repLabel = "Moderate Trust / Neutral Author";
  let repBadgeStyle = "bg-amber-500/20 text-amber-300 border border-amber-500/40";
  let repCardStyle = "border-amber-500/40 bg-gradient-to-r from-amber-950/20 to-slate-900/60";
  let repIconBg = "bg-amber-500/20 text-amber-400 shadow-amber-500/20";
  let repTextColor = "text-amber-400";

  if (repScore >= 70) {
    repLabel = "Verified Trustworthy Author";
    repBadgeStyle = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
    repCardStyle = "border-emerald-500/40 bg-gradient-to-r from-emerald-950/20 to-slate-900/60";
    repIconBg = "bg-emerald-500/20 text-emerald-400 shadow-emerald-500/20";
    repTextColor = "text-emerald-400";
  } else if (repScore < 30) {
    repLabel = "High Fraud Risk Author";
    repBadgeStyle = "bg-rose-500/20 text-rose-300 border border-rose-500/40";
    repCardStyle = "border-rose-500/40 bg-gradient-to-r from-rose-950/20 to-slate-900/60";
    repIconBg = "bg-rose-500/20 text-rose-400 shadow-rose-500/20";
    repTextColor = "text-rose-400";
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fadeIn">
      
      {/* Back Button */}
      <button 
        onClick={onBack}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-sm font-medium mb-8 transition-all hover:-translate-x-1"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back</span>
      </button>

      {/* Reviewer Profile Hero Card */}
      <div className={`glass-card rounded-3xl p-8 mb-10 relative overflow-hidden border-2 ${repCardStyle}`}>
        <div className={`absolute top-0 right-0 w-96 h-96 rounded-full blur-3xl pointer-events-none ${
          repScore >= 70 ? 'bg-emerald-500/10' : (repScore < 30 ? 'bg-rose-500/10' : 'bg-amber-500/10')
        }`} />

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div className="flex items-start gap-5">
            <div className={`w-20 h-20 rounded-3xl flex items-center justify-center flex-shrink-0 shadow-lg ${repIconBg}`}>
              <User className="w-10 h-10" />
            </div>
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono font-medium">
                  <Building2 className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Submitter: {reviewer?.submitter_id || reviews[0]?.submitter_id || "AMAZON_US"}</span>
                </span>
                <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${repBadgeStyle}`}>
                  {repLabel}
                </span>
              </div>
              <h2 className="text-3xl font-extrabold text-white tracking-tight">
                {reviewer?.name || reviews[0]?.reviewer_name || `Reviewer ${reviewerId}`}
              </h2>
              <div className="flex items-center gap-2 mt-1 font-mono text-xs">
                <span className="text-slate-400">Universal Keccak ID:</span>
                <strong className="text-slate-200 select-all">{reviewer?.universal_reviewer_id || reviewerId}</strong>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigator.clipboard.writeText(reviewer?.universal_reviewer_id || reviewerId);
                  }}
                  title="Copy full Universal Keccak ID"
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-cyan-400 transition-colors text-xs"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy</span>
                </button>
              </div>
            </div>
          </div>

          {/* Reputation Stats Box */}
          <div className="flex items-center gap-4 bg-slate-900/90 border border-slate-800 p-5 rounded-2xl">
            <div className="text-center px-5 border-r border-slate-800">
              <span className="text-xs text-slate-400 block mb-1 uppercase tracking-wider font-semibold">Reputation Rating</span>
              <div className="flex items-center justify-center gap-1">
                <Award className={`w-6 h-6 ${repTextColor}`} />
                <span className={`font-extrabold text-3xl font-mono ${repTextColor}`}>
                  {repScore}/100
                </span>
              </div>
            </div>
            <div className="text-center px-4">
              <span className="text-xs text-slate-400 block mb-1 uppercase tracking-wider font-semibold">Total Reviews</span>
              <span className="font-extrabold text-3xl text-white font-mono">
                {reviewer?.review_count || reviews.length}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Reviews List Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-2xl font-bold text-white">Submitted Review Audit Trail</h3>
          <p className="text-sm text-slate-400 mt-0.5">
            All reviews written by this author across products, with AI fraud scores and Alastria mining hashes.
          </p>
        </div>
        <span className="bg-slate-800 text-slate-300 text-xs font-bold px-3 py-1 rounded-full border border-slate-700">
          {reviews.length} Records
        </span>
      </div>

      {/* Reviews List */}
      {reviews.length === 0 ? (
        <div className="text-center py-16 glass-card rounded-3xl">
          <p className="text-slate-400">No reviews found for this author.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((rev) => {
            return (
              <div 
                key={rev.universal_review_id}
                className="glass-card rounded-3xl p-6 transition-all border-l-4 border-l-cyan-500 bg-slate-900/40"
              >
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  
                  <div className="flex-1 space-y-3">
                    {/* Product & Rating */}
                    <div className="flex items-center flex-wrap gap-3">
                      <span className="px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-cyan-300 font-semibold text-xs font-mono">
                        Product: {rev.product_name || rev.product_id}
                      </span>
                      <div className="flex items-center gap-1 bg-slate-900/80 px-2.5 py-1 rounded-full border border-slate-800 text-xs font-bold text-amber-400">
                        <Star className="w-3.5 h-3.5 fill-amber-400" />
                        <span>{rev.rating ? rev.rating.toFixed(1) : "5.0"}</span>
                      </div>
                      {rev.review_date && (
                        <div className="flex items-center gap-1 text-xs text-slate-400">
                          <Calendar className="w-3.5 h-3.5" />
                          <span>{new Date(rev.review_date).toLocaleDateString()}</span>
                        </div>
                      )}
                    </div>

                    {/* Review Text */}
                    <p className="text-slate-200 text-sm md:text-base leading-relaxed">
                      "{rev.review_text || "No written review content provided."}"
                    </p>

                    {/* Cryptographic Badges */}
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

                      {rev.tx_hash ? (
                        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-cyan-950/60 border border-cyan-500/40 text-[11px] font-mono text-cyan-300">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                          <span>Alastria Red T Tx: {rev.tx_hash}</span>
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
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
