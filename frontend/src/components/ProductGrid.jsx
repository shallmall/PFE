import React from 'react';
import ProductCard from './ProductCard';
import { PackageSearch } from 'lucide-react';

export default function ProductGrid({ products, searchQuery, onSelectProduct, loading }) {
  const filtered = products.filter((p) =>
    p.product_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.product_id && p.product_id.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 flex flex-col items-center justify-center min-h-[400px]">
        <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4" />
        <p className="text-slate-600 font-medium">Fetching verified catalog from AI Ledger...</p>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 text-slate-400 mb-4">
          <PackageSearch className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-bold text-slate-800 mb-1">No products found</h3>
        <p className="text-slate-500 text-sm max-w-md mx-auto">
          We couldn't find any items matching "{searchQuery}". Try searching for another keyword or ASIN.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Verified Catalog</h2>
          <p className="text-sm text-slate-500">
            Showing <span className="font-semibold text-slate-800">{filtered.length}</span> products authenticated by Late Fusion AI & Alastria Blockchain
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {filtered.map((prod) => (
          <ProductCard
            key={prod.product_id}
            product={prod}
            onSelect={onSelectProduct}
          />
        ))}
      </div>
    </div>
  );
}
