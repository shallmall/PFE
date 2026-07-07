import React from 'react';
import { ShieldCheck, AlertTriangle, ShieldAlert, Star, Building2, ChevronRight } from 'lucide-react';

export default function ProductCard({ product, onSelect }) {
  const score = product.product_score ?? 50;

  // Determine reputation color and label based on 0-100 scale
  const getReputationBadge = (val) => {
    if (val >= 80) {
      return {
        color: "bg-emerald-500/10 text-emerald-700 border-emerald-300",
        barColor: "bg-emerald-500",
        label: "Verified High Trust",
        icon: <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
      };
    } else if (val >= 55) {
      return {
        color: "bg-blue-500/10 text-blue-700 border-blue-300",
        barColor: "bg-blue-500",
        label: "Verified Standard",
        icon: <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
      };
    } else if (val >= 35) {
      return {
        color: "bg-amber-500/10 text-amber-700 border-amber-300",
        barColor: "bg-amber-500",
        label: "Suspicious Activity",
        icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
      };
    } else {
      return {
        color: "bg-rose-500/10 text-rose-700 border-rose-300",
        barColor: "bg-rose-500",
        label: "High Bot/Spam Risk",
        icon: <ShieldAlert className="w-3.5 h-3.5 text-rose-600 animate-bounce" />
      };
    }
  };

  const badge = getReputationBadge(score);
  const percentage = Math.min(Math.round(score), 100);

  return (
    <div
      onClick={() => onSelect(product)}
      className="group bg-white rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-xl hover:border-indigo-300/80 transition-all duration-300 overflow-hidden flex flex-col cursor-pointer"
    >
      {/* Image Banner */}
      <div className="relative h-48 bg-slate-100 overflow-hidden">
        {product.image ? (
          <img
            src={product.image}
            alt={product.product_name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 text-slate-400 font-medium">
            No Image
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-80" />
        
        {/* Price & Category overlay */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between text-white">
          <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-black/40 backdrop-blur-md">
            {product.category || "General"}
          </span>
          <span className="text-sm font-bold tracking-tight bg-indigo-600 px-2.5 py-0.5 rounded-lg shadow-sm">
            {product.price || "$99.99"}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="p-5 flex-1 flex flex-col justify-between gap-4">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 mb-1.5">
            <Building2 className="w-3.5 h-3.5 text-slate-400" />
            <span>Submitter:</span>
            <code className="text-[11px] font-mono font-semibold bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">
              {product.submitter_id}
            </code>
          </div>
          <h3 className="font-bold text-slate-900 line-clamp-2 text-base group-hover:text-indigo-600 transition-colors">
            {product.product_name}
          </h3>
        </div>

        {/* Reputation Score Section */}
        <div className="pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between mb-1.5">
            <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs font-bold ${badge.color}`}>
              {badge.icon}
              <span>{badge.label}</span>
            </div>
            <div className="text-right">
              <span className="text-xs font-semibold text-slate-500">Reviewee Score: </span>
              <span className="font-mono font-extrabold text-slate-900 text-sm">{score}</span>
              <span className="text-[10px] text-slate-400">/100</span>
            </div>
          </div>

          {/* Progress Gauge */}
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-700 rounded-full ${badge.barColor}`}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between pt-1 text-xs font-semibold text-indigo-600 group-hover:translate-x-0.5 transition-transform">
          <span>View Verified Reviews ({product.reviews?.length || product.num_reviews || 0})</span>
          <ChevronRight className="w-4 h-4" />
        </div>
      </div>
    </div>
  );
}
