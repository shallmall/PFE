import React, { useState, useEffect } from "react";
import {
  X,
  UserCheck,
  UserX,
  ShieldCheck,
  ShieldAlert,
  Star,
  ExternalLink,
  KeyRound,
  Package,
  Award,
  MessageSquare,
  Hash,
  Database,
  ArrowRight,
  CheckCircle
} from "lucide-react";

export default function ReviewerProfileModal({ isOpen, onClose, reviewerId, reviewerName, useLiveApi }) {
  const [loading, setLoading] = useState(true);
  const [profileData, setProfileData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !reviewerId) return;

    const fetchReviewerProfile = async () => {
      setLoading(true);
      setError(null);
      try {
        if (useLiveApi) {
          const res = await fetch(`http://localhost:8000/api/v1/reviews/reviewer/${encodeURIComponent(reviewerId)}`);
          if (!res.ok) {
            throw new Error(`Failed to load reviewer profile (Status: ${res.status})`);
          }
          const data = await res.json();
          setProfileData(data);
        } else {
          // Fallback static demonstration profile
          setProfileData({
            reviewer_id: reviewerId,
            reviewer_name: reviewerName || reviewerId,
            universal_reviewer_id: "0x4fdcca5ddb678139",
            reviewer_score: 88,
            reviews: [
              {
                universal_review_id: "0xrev_demo_001",
                reviewee_name: "Sony Wireless Noise Canceling Headphones",
                reviewee_id: "ASIN_B08N5WRWNW",
                universal_reviewee_id: "0x91987eda86b87fdf",
                reviewee_score: 94,
                review_rating: 5.0,
                review_text: "Outstanding build quality and noise cancellation. Battery lasts for days of heavy work calls.",
                ai_score: 91,
                tx_hash: "0x87eebe9eec67728cb228a834fd370b58d8ebd677280eed2eb2d9ffb408edff00"
              },
              {
                universal_review_id: "0xrev_demo_002",
                reviewee_name: "Logitech MX Master 3S Advanced Ergonomic Mouse",
                reviewee_id: "ASIN_B09HMKP17D",
                universal_reviewee_id: "0xaa4422bb998811cc",
                reviewee_score: 92,
                review_rating: 5.0,
                review_text: "The electromagnetic scroll wheel is super fast and precise. Highly recommended for developers.",
                ai_score: 87,
                tx_hash: "0xf9228809d540c85c9cb54f43d8833c2d53c0a372152168361e72db4a268a1fc6"
              }
            ]
          });
        }
      } catch (err) {
        console.error("Error fetching reviewer:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchReviewerProfile();
  }, [isOpen, reviewerId, useLiveApi]);

  if (!isOpen) return null;

  const normScore = (v) => {
    if (v === undefined || v === null || isNaN(v)) return 50;
    let n = Number(v);
    if (n > 100) n = Math.round((n / 255) * 100);
    return Math.max(0, Math.min(100, Math.round(n)));
  };

  const score = normScore(profileData?.reviewer_score ?? 50);
  const isHighTrust = score >= 75;
  const isTrusted = score >= 55;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-white rounded-3xl w-full max-w-4xl p-6 shadow-2xl border border-slate-100 flex flex-col max-h-[92vh] overflow-hidden">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 text-white flex items-center justify-center shadow-md">
              <UserCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-extrabold text-slate-900">{profileData?.reviewer_name || reviewerId}</h3>
                <span className="bg-indigo-50 text-indigo-700 text-xs px-2.5 py-0.5 rounded-full font-semibold border border-indigo-200">
                  Verified Reviewer
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">ID: {reviewerId}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center py-24">
            <div className="w-12 h-12 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin mb-4" />
            <p className="text-slate-500 text-sm font-medium animate-pulse">Consulting Alastria Blockchain Ledger...</p>
          </div>
        ) : error ? (
          <div className="flex-1 flex flex-col items-center justify-center py-20 text-center px-4">
            <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-full flex items-center justify-center mb-4">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <h4 className="text-base font-bold text-slate-800 mb-1">Failed to retrieve reviewer profile</h4>
            <p className="text-xs text-slate-500 max-w-md">{error}</p>
          </div>
        ) : profileData && (
          <div className="flex-1 overflow-y-auto space-y-6 pr-1">
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              
              <div className="md:col-span-1 p-5 rounded-3xl bg-gradient-to-br from-slate-900 to-slate-800 text-white flex flex-col justify-between shadow-md">
                <div className="flex items-center justify-between text-slate-400 mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider">Reviewer Reputation</span>
                  <Award className="w-5 h-5 text-indigo-400" />
                </div>
                <div className="flex items-baseline gap-2 my-2">
                  <span className="text-5xl font-black text-white font-mono">{score}</span>
                  <span className="text-sm font-bold text-slate-400">/ 100</span>
                </div>
                <div className="w-full h-2.5 bg-slate-700 rounded-full overflow-hidden my-2">
                  <div
                    className={`h-full rounded-full ${isHighTrust ? "bg-emerald-400" : isTrusted ? "bg-blue-400" : "bg-rose-500"}`}
                    style={{ width: `${Math.min(score, 100)}%` }}
                  />
                </div>
                <div className="mt-2 flex items-center justify-between text-xs font-bold">
                  <span className={isHighTrust ? "text-emerald-400" : isTrusted ? "text-blue-400" : "text-rose-400"}>
                    {isHighTrust ? "High Trust Reviewer" : isTrusted ? "Verified Authentic" : "High Risk Actor"}
                  </span>
                </div>
              </div>

              {/* Cryptographic & Ledger Stats */}
              <div className="md:col-span-2 p-5 rounded-3xl bg-slate-50 border border-slate-200/80 flex flex-col justify-between space-y-3">
                <div className="flex items-center justify-between border-b border-slate-200/60 pb-3">
                  <div>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Universal Reviewer Hash</span>
                    <p className="font-mono text-xs font-bold text-slate-700 truncate max-w-sm mt-0.5">
                      {profileData.universal_reviewer_id || "0x0"}
                    </p>
                  </div>
                  <span className="px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> Registered
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-1">
                  <div>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Total Evaluations</span>
                    <p className="text-lg font-black text-slate-900 mt-0.5">
                      {profileData.reviews?.length || 0} <span className="text-xs font-medium text-slate-500">anchored</span>
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Consensus Engine</span>
                    <p className="text-xs font-bold text-indigo-600 mt-1 flex items-center gap-1">
                      Alastria Quorum IBFT 2.0
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Section Header */}
            <div className="flex items-center justify-between pt-2">
              <h4 className="font-extrabold text-slate-800 text-base flex items-center gap-2">
                <span>Submitted Reviews History</span>
                <span className="bg-slate-100 text-slate-700 text-xs px-2.5 py-0.5 rounded-full font-mono font-bold">
                  {profileData.reviews?.length || 0}
                </span>
              </h4>
              <span className="text-xs text-slate-400">Chronological Ledger Order</span>
            </div>

            {/* Reviews List */}
            <div className="space-y-4">
              {(!profileData.reviews || profileData.reviews.length === 0) ? (
                <div className="text-center py-12 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                  <p className="text-slate-500 text-sm">No review history found for this user.</p>
                </div>
              ) : (
                profileData.reviews.map((rev, idx) => {
                  const revScore = normScore(rev.ai_score ?? 50);
                  const isRevPassed = revScore >= 55;
                  const revieweeScore = normScore(rev.reviewee_score ?? 50);
                  const isProdPassed = revieweeScore >= 55;

                  return (
                    <div
                      key={rev.universal_review_id || idx}
                      className="p-5 rounded-3xl bg-white border border-slate-200 shadow-sm hover:border-indigo-300 transition-all space-y-4"
                    >
                      {/* Top Header: Target Reviewee Info Box */}
                      <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200/80 flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-start gap-3">
                          <div className="p-2.5 bg-indigo-100 text-indigo-700 rounded-xl mt-0.5">
                            <Package className="w-5 h-5" />
                          </div>
                          <div>
                            <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">Reviewed Target / Product</span>
                            <h4 className="text-sm font-extrabold text-slate-900 line-clamp-1">{rev.reviewee_name || "Target Product"}</h4>
                            <div className="flex items-center gap-2 mt-1">
                              <code className="text-[11px] font-mono font-bold text-slate-600 bg-white px-2 py-0.5 rounded border border-slate-200">
                                ID: {rev.reviewee_id}
                              </code>
                              {rev.universal_reviewee_id && (
                                <code className="text-[10px] font-mono text-slate-400 truncate max-w-[150px]" title={rev.universal_reviewee_id}>
                                  ({rev.universal_reviewee_id})
                                </code>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Reviewee Score Badge */}
                        <div className="flex items-center gap-2">
                          <div className={`px-3 py-1.5 rounded-xl border text-xs font-extrabold flex items-center gap-1.5 shadow-2xs ${
                            isProdPassed
                              ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                              : "bg-rose-50 text-rose-800 border-rose-300"
                          }`}>
                            <span>Reviewee Score:</span>
                            <span className="font-mono text-sm">{revieweeScore}/100</span>
                          </div>
                        </div>
                      </div>

                      {/* Review Comment & Rating Row */}
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex items-center gap-1 text-amber-500">
                          {[...Array(5)].map((_, i) => (
                            <Star
                              key={i}
                              className={`w-4 h-4 ${i < Math.floor(rev.review_rating || 5) ? "fill-amber-400" : "text-slate-200"}`}
                            />
                          ))}
                          <span className="text-xs font-black text-slate-800 ml-1.5">{rev.review_rating || 5.0}</span>
                        </div>

                        {/* Individual Review AI Score */}
                        <div className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 border ${
                          isRevPassed ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"
                        }`}>
                          {isRevPassed ? <ShieldCheck className="w-3.5 h-3.5" /> : <ShieldAlert className="w-3.5 h-3.5" />}
                          <span>Review Trust Score: {revScore}/100</span>
                        </div>
                      </div>

                      {/* Comment Body */}
                      <p className="text-slate-700 text-sm leading-relaxed bg-slate-50/50 p-3.5 rounded-2xl border border-slate-100">
                        "{rev.review_text}"
                      </p>

                      {/* Footer: On-Chain Anchor & All 3 IDs */}
                      <div className="pt-3 border-t border-slate-100 space-y-2">
                        <div className="flex items-center gap-1 font-mono text-[11px] truncate" title={rev.tx_hash}>
                          <Hash className="w-3.5 h-3.5 text-indigo-500" />
                          <span className="text-slate-500 font-semibold">Alastria Hash:</span>
                          <span className="text-indigo-600 font-semibold truncate">{rev.tx_hash || "0xAnchoredStorageSlot"}</span>
                        </div>
                        
                        <div className="flex flex-wrap items-center gap-2 font-mono text-[10px] pt-1.5 border-t border-slate-100/60 justify-between">
                          <div className="flex items-center gap-1">
                            <span className="text-slate-400 font-semibold">1. Review ID:</span>
                            <code className="bg-slate-100 text-slate-700 font-bold px-1.5 py-0.5 rounded">{rev.universal_review_id || "0x0"}</code>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-slate-400 font-semibold">2. Reviewer ID:</span>
                            <code className="bg-indigo-50 text-indigo-700 font-bold px-1.5 py-0.5 rounded border border-indigo-200">{profileData.reviewer_id}</code>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-slate-400 font-semibold">3. Reviewee ID:</span>
                            <code className="bg-emerald-50 text-emerald-700 font-bold px-1.5 py-0.5 rounded border border-emerald-200">{rev.reviewee_id}</code>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
