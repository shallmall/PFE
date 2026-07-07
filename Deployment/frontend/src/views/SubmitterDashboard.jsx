import React, { useState } from 'react';
import { BarChart3, CheckCircle2, ShieldAlert, Users, Package, FileText, ArrowLeft, Building2, Award, Hash } from 'lucide-react';

export default function SubmitterDashboard({ reportData, onBackToCatalog, onSelectProduct, onSelectReviewer }) {
  const [activeTab, setActiveTab] = useState('reviewers'); // 'reviewers', 'products', 'results'

  if (!reportData) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-400">No active submission report. Submit a review batch to view dashboard results.</p>
        <button onClick={onBackToCatalog} className="mt-4 px-6 py-2 bg-cyan-600 text-white rounded-xl">Go to Catalog</button>
      </div>
    );
  }

  const cleanCount = reportData.total_processed - reportData.fraud_detected;
  const fraudRate = reportData.total_processed > 0 ? Math.round((reportData.fraud_detected / reportData.total_processed) * 100) : 0;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 animate-fadeIn">
      
      {/* Top Bar */}
      <div className="flex items-center justify-between mb-8">
        <button 
          onClick={onBackToCatalog}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 text-sm font-medium transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Return to Product Catalog</span>
        </button>
        <span className="px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
          Live AI & Web3 Ledger Report
        </span>
      </div>

      {/* Hero Summary Banner */}
      <div className="glass-card rounded-3xl p-8 mb-8 relative overflow-hidden border-emerald-500/30">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-cyan-300 font-mono text-xs font-semibold">
                <Building2 className="w-3.5 h-3.5 text-cyan-400" />
                <span>Submitter: {reportData.submitter_id}</span>
              </span>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 text-xs font-semibold">
                Batch Verified
              </span>
            </div>
            <h2 className="text-3xl font-extrabold text-white tracking-tight">
              Enterprise Batch Submission Report
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Late Fusion AI classification results and Alastria Red T reputation adjustments for your batch.
            </p>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-3 gap-3 bg-slate-900/90 border border-slate-800 p-4 rounded-2xl">
            <div className="text-center px-4 border-r border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Total Processed</span>
              <span className="font-extrabold text-2xl text-white font-mono">{reportData.total_processed}</span>
            </div>
            <div className="text-center px-4 border-r border-slate-800">
              <span className="text-xs text-slate-400 block mb-1">Clean / Genuine</span>
              <span className="font-extrabold text-2xl text-emerald-400 font-mono">{cleanCount}</span>
            </div>
            <div className="text-center px-4">
              <span className="text-xs text-slate-400 block mb-1">Fraud Ring Risk</span>
              <span className={`font-extrabold text-2xl font-mono ${fraudRate > 20 ? 'text-rose-400' : 'text-amber-400'}`}>
                {reportData.fraud_detected} <span className="text-xs font-normal">({fraudRate}%)</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-3 mb-6 border-b border-slate-800 pb-4 overflow-x-auto">
        <button
          onClick={() => setActiveTab('reviewers')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl font-semibold text-sm transition-all ${
            activeTab === 'reviewers'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
              : 'bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Tab 1: Reviewers Reputations</span>
          <span className="bg-black/30 px-2 py-0.5 rounded-full text-xs ml-1">{reportData.reviewers_scores?.length || 0}</span>
        </button>

        <button
          onClick={() => setActiveTab('products')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl font-semibold text-sm transition-all ${
            activeTab === 'products'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
              : 'bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <Package className="w-4 h-4" />
          <span>Tab 2: Products Quality</span>
          <span className="bg-black/30 px-2 py-0.5 rounded-full text-xs ml-1">{reportData.products_scores?.length || 0}</span>
        </button>

        <button
          onClick={() => setActiveTab('results')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl font-semibold text-sm transition-all ${
            activeTab === 'results'
              ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/20'
              : 'bg-slate-900/60 text-slate-400 hover:text-white hover:bg-slate-800'
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>Tab 3: Review Audit Log</span>
          <span className="bg-black/30 px-2 py-0.5 rounded-full text-xs ml-1">{reportData.results?.length || 0}</span>
        </button>
      </div>

      {/* Tab 1: Reviewers Score Summary */}
      {activeTab === 'reviewers' && (
        <div className="glass-card rounded-3xl overflow-hidden border border-slate-800">
          <div className="p-6 bg-slate-900/50 border-b border-slate-800">
            <h3 className="text-lg font-bold text-white">Reviewer Reputation Ratings</h3>
            <p className="text-xs text-slate-400 mt-0.5">Updated 3-Variable author reputation scores based on historical DeBERTa spam risk and GNN graph counts.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-mono">
                <tr>
                  <th className="p-4">Reviewer ID</th>
                  <th className="p-4">Name</th>
                  <th className="p-4 text-center">Reputation Score</th>
                  <th className="p-4 text-center">Reviews</th>
                  <th className="p-4 text-center">Fake Detected</th>
                  <th className="p-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {reportData.reviewers_scores?.map((rev) => {
                  const rep = Math.round((rev.current_score || 0) * 100);
                  let badgeClass = "bg-amber-500/20 text-amber-400 border border-amber-500/30";
                  if (rep >= 70) badgeClass = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                  else if (rep < 30) badgeClass = "bg-rose-500/20 text-rose-400 border border-rose-500/30";
                  
                  return (
                    <tr key={rev.universal_reviewer_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-4 font-bold text-cyan-400">{rev.reviewer_id}</td>
                      <td className="p-4 text-slate-200 font-sans">{rev.name || "Anonymous Reviewer"}</td>
                      <td className="p-4 text-center">
                        <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full font-bold text-xs ${badgeClass}`}>
                          <Award className="w-3.5 h-3.5" />
                          <span>{rep}/100</span>
                        </span>
                      </td>
                      <td className="p-4 text-center text-slate-300">{rev.review_count}</td>
                      <td className={`p-4 text-center font-bold ${rev.fraud_count > 0 ? 'text-rose-400' : 'text-slate-500'}`}>
                        {rev.fraud_count}
                      </td>
                      <td className="p-4 text-right font-sans">
                        <button 
                          onClick={() => onSelectReviewer(rev.reviewer_id)}
                          className="text-xs text-cyan-400 hover:text-cyan-300 underline font-semibold"
                        >
                          View Profile
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Products Score Summary */}
      {activeTab === 'products' && (
        <div className="glass-card rounded-3xl overflow-hidden border border-slate-800">
          <div className="p-6 bg-slate-900/50 border-b border-slate-800">
            <h3 className="text-lg font-bold text-white">Product Quality & AI Risk Averages</h3>
            <p className="text-xs text-slate-400 mt-0.5">Aggregated star ratings vs Late Fusion AI fraud probabilities across monitored products.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-mono">
                <tr>
                  <th className="p-4">Product ID</th>
                  <th className="p-4">Product Name</th>
                  <th className="p-4">Category</th>
                  <th className="p-4 text-center">Avg Rating</th>
                  <th className="p-4 text-center">AI Fraud Risk</th>
                  <th className="p-4 text-center">Reviews</th>
                  <th className="p-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {reportData.products_scores?.map((prod) => {
                  const risk = Math.round((prod.avg_ai_score || 0) * 100);
                  let riskClass = "bg-amber-500/20 text-amber-400 border border-amber-500/30";
                  let riskText = "Inconclusive";
                  if (risk < 30) {
                    riskClass = "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
                    riskText = "Verified Authentic";
                  } else if (risk > 80) {
                    riskClass = "bg-rose-500/20 text-rose-400 border border-rose-500/30";
                    riskText = "High Fraud Risk";
                  }
                  
                  return (
                    <tr key={prod.universal_product_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-4 font-bold text-cyan-400">{prod.product_id}</td>
                      <td className="p-4 text-slate-200 font-sans font-semibold">{prod.name || `Product ${prod.product_id}`}</td>
                      <td className="p-4 text-slate-400 font-sans">{prod.category || "General"}</td>
                      <td className="p-4 text-center text-amber-400 font-bold">{prod.avg_rating.toFixed(1)} / 5.0</td>
                      <td className="p-4 text-center">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-bold text-xs ${riskClass}`}>
                          <span>{risk}% ({riskText})</span>
                        </span>
                      </td>
                      <td className="p-4 text-center text-slate-300">{prod.review_count}</td>
                      <td className="p-4 text-right font-sans">
                        <button 
                          onClick={() => onSelectProduct(prod)}
                          className="text-xs text-cyan-400 hover:text-cyan-300 underline font-semibold"
                        >
                          Inspect Log
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Review Audit Log */}
      {activeTab === 'results' && (
        <div className="glass-card rounded-3xl overflow-hidden border border-slate-800">
          <div className="p-6 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-white">Batch Review Classification Results</h3>
              <p className="text-xs text-slate-400 mt-0.5">Individual review fraud scores and smart contract transaction anchors.</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/60 text-slate-400 uppercase text-xs font-mono">
                <tr>
                  <th className="p-4">Review ID</th>
                  <th className="p-4 text-center">AI Fraud Score</th>
                  <th className="p-4 text-center">DeBERTa Spam</th>
                  <th className="p-4 text-center">Status</th>
                  <th className="p-4">Alastria Web3 Tx Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                {reportData.results?.map((res) => {
                  const score = Math.round((res.ai_score || 0) * 100);
                  let scoreClass = "bg-amber-950/80 text-amber-300 border border-amber-800";
                  let scoreLabel = "Inconclusive";
                  if (score < 30) {
                    scoreClass = "bg-emerald-950/80 text-emerald-300 border border-emerald-800";
                    scoreLabel = "Verified Authentic";
                  } else if (score > 80) {
                    scoreClass = "bg-rose-950/80 text-rose-300 border border-rose-800";
                    scoreLabel = "High Fraud Probability";
                  }
                  
                  return (
                    <tr key={res.review_id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="p-4 font-bold text-white">{res.review_id}</td>
                      <td className="p-4 text-center">
                        <span className={`px-2.5 py-1 rounded font-bold ${scoreClass}`}>
                          {score}% ({scoreLabel})
                        </span>
                      </td>
                      <td className="p-4 text-center text-slate-400">
                        {Math.round((res.deberta_prob || 0) * 100)}%
                      </td>
                      <td className="p-4 text-center text-cyan-400 font-semibold">{res.status || "Confirmed"}</td>
                      <td className="p-4 text-slate-400">
                        {res.tx_hash ? (
                          <span className="text-emerald-400 font-mono bg-slate-900 px-2 py-1 rounded border border-slate-800">
                            {res.tx_hash.slice(0, 24)}...
                          </span>
                        ) : (
                          <span className="text-amber-400 font-mono">Pending Anchor</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
