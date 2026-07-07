import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ProductGrid from './components/ProductGrid';
import ProductDetailModal from './components/ProductDetailModal';
import BatchUploadModal from './components/BatchUploadModal';
import ReviewerProfileModal from './components/ReviewerProfileModal';
import { MOCK_PRODUCTS } from './mockData';

export default function App() {
  const loadInitialProducts = () => {
    try {
      const saved = localStorage.getItem("verified_store_catalog");
      if (saved) {
        return JSON.parse(saved);
      }
    } catch (e) {
      console.error("Error reading catalog from localStorage", e);
    }
    return MOCK_PRODUCTS;
  };

  const [products, setProducts] = useState(loadInitialProducts);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [selectedReviewer, setSelectedReviewer] = useState(null);
  const [isPortalOpen, setIsPortalOpen] = useState(false);
  const [useLiveApi, setUseLiveApi] = useState(true);
  const [loading, setLoading] = useState(false);

  // Fetch from live API when useLiveApi is enabled
  useEffect(() => {
    if (useLiveApi) {
      setLoading(true);
      fetch("http://localhost:8000/api/v1/products")
        .then((res) => {
          if (!res.ok) throw new Error("API Offline");
          return res.json();
        })
        .then((data) => {
          // Enrich with mock images if live product doesn't have one
          const enriched = data.map((p, idx) => ({
            ...p,
            image: MOCK_PRODUCTS[idx % MOCK_PRODUCTS.length]?.image || "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=600&auto=format&fit=crop&q=80",
            category: "Verified Ledger Item",
            price: "$149.99"
          }));
          setProducts(enriched);
        })
        .catch(() => {
          // Fallback to local stored catalog if live backend isn't running
          setProducts(loadInitialProducts());
        })
        .finally(() => setLoading(false));
    } else {
      setProducts(loadInitialProducts());
    }
  }, [useLiveApi]);

  // Handle clicking product card to load reviews
  const handleSelectProduct = async (prod) => {
    if (useLiveApi && prod.product_id) {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/reviews/product/${prod.product_id}`);
        if (res.ok) {
          const detailData = await res.json();
          setSelectedProduct({
            ...prod,
            reviews: detailData.reviews
          });
          return;
        }
      } catch (e) {
        console.error("Failed to load product reviews from live API", e);
      }
    }
    setSelectedProduct(prod);
  };

  // Handle successful batch upload
  const handleBatchSuccess = (newRecords) => {
    if (!newRecords || newRecords.length === 0) return;

    // Group incoming records by reviewee_id (product ID)
    const grouped = {};
    newRecords.forEach((r) => {
      const pid = r.reviewee_id || r.product_id || "ASIN_PORTAL_BATCH";
      if (!grouped[pid]) grouped[pid] = [];
      grouped[pid].push(r);
    });

    setProducts((prevProducts) => {
      let updatedList = [...prevProducts];

      const imagesPool = [
        "https://images.unsplash.com/photo-1593941707882-a5bba14938c7?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=600&auto=format&fit=crop&q=80",
        "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&auto=format&fit=crop&q=80"
      ];

      Object.keys(grouped).forEach((pid, idx) => {
        const prodReviews = grouped[pid];
        const existingIdx = updatedList.findIndex(p => p.product_id === pid);

        const formattedReviews = prodReviews.map((r) => ({
          universal_review_id: r.universal_review_id,
          reviewer_name: r.reviewer_name || r.reviewer_id,
          reviewer_id: r.reviewer_id,
          reviewer_score: r.reviewer_score ?? r.ai_score ?? 50,
          review_rating: r.review_rating || 5.0,
          review_text: r.review_text || "",
          ai_score: r.ai_score ?? 50,
          created_at: r.created_at || new Date().toISOString(),
          payload_hash: r.payload_hash,
          recovered_public_key: r.recovered_public_key
        }));

        if (existingIdx !== -1) {
          // Update existing product
          const existing = updatedList[existingIdx];
          const combinedReviews = [...formattedReviews, ...(existing.reviews || [])];
          const avgScore = Math.round(combinedReviews.reduce((sum, rev) => sum + (rev.ai_score || 50), 0) / combinedReviews.length);

          updatedList[existingIdx] = {
            ...existing,
            product_score: avgScore,
            num_reviews: combinedReviews.length,
            reviews: combinedReviews
          };
        } else {
          // Brand new product card from CSV/JSON!
          const avgScore = Math.round(formattedReviews.reduce((sum, rev) => sum + (rev.ai_score || 50), 0) / formattedReviews.length);
          const newProduct = {
            product_id: pid,
            product_name: prodReviews[0].reviewee_name || prodReviews[0].product_name || `Uploaded Item (${pid})`,
            category: "Batch Ingested Product",
            price: "$129.99",
            image: imagesPool[idx % imagesPool.length],
            submitter_id: prodReviews[0].submitter_id || "Partner API",
            product_score: avgScore,
            num_reviews: formattedReviews.length,
            reviews: formattedReviews
          };
          updatedList.unshift(newProduct);
        }
      });

      // Save to localStorage so uploaded items persist across refreshes!
      try {
        localStorage.setItem("verified_store_catalog", JSON.stringify(updatedList));
      } catch (e) {
        console.error("Failed to save updated catalog to localStorage", e);
      }

      return updatedList;
    });
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 font-sans selection:bg-indigo-500 selection:text-white">
      <Header
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onOpenPortal={() => setIsPortalOpen(true)}
        onOpenReviewerDemo={(rev) => setSelectedReviewer(rev)}
        useLiveApi={useLiveApi}
        setUseLiveApi={setUseLiveApi}
      />

      <main className="flex-1">
        <ProductGrid
          products={products}
          searchQuery={searchQuery}
          onSelectProduct={handleSelectProduct}
          loading={loading}
        />
      </main>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
          onSelectReviewer={(rev) => setSelectedReviewer(rev)}
        />
      )}

      {/* Batch Upload Modal */}
      <BatchUploadModal
        isOpen={isPortalOpen}
        onClose={() => setIsPortalOpen(false)}
        useLiveApi={useLiveApi}
        onUploadSuccess={handleBatchSuccess}
        onSelectReviewer={(rev) => setSelectedReviewer(rev)}
      />

      {/* Reviewer Showcase Profile Modal */}
      <ReviewerProfileModal
        isOpen={!!selectedReviewer}
        onClose={() => setSelectedReviewer(null)}
        reviewerId={selectedReviewer?.id}
        reviewerName={selectedReviewer?.name}
        useLiveApi={useLiveApi}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-12">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>© 2026 VerifiedStore Inc. Powered by Late Fusion AI & Alastria Red T Blockchain.</p>
          <div className="flex items-center gap-4">
            <span>EVM Consortium Verified</span>
            <span>•</span>
            <span>Zero-Gas Protocol</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
