import React, { useState } from 'react';
import Navbar from './components/Navbar';
import SubmissionModal from './components/SubmissionModal';
import ProductCatalog from './views/ProductCatalog';
import ProductDetail from './views/ProductDetail';
import ReviewerProfile from './views/ReviewerProfile';
import SubmitterDashboard from './views/SubmitterDashboard';

export default function App() {
  const [currentView, setCurrentView] = useState('catalog'); // 'catalog', 'product_detail', 'reviewer_profile', 'dashboard'
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [selectedReviewerId, setSelectedReviewerId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [dashboardReport, setDashboardReport] = useState(null);

  const handleSelectProduct = (product) => {
    setSelectedProduct(product);
    setCurrentView('product_detail');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSelectReviewer = (reviewerId) => {
    setSelectedReviewerId(reviewerId);
    setCurrentView('reviewer_profile');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSubmissionSuccess = (reportData) => {
    setDashboardReport(reportData);
    setCurrentView('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen flex flex-col justify-between selection:bg-cyan-500 selection:text-white">
      
      {/* Top Navigation */}
      <Navbar
        currentView={currentView}
        setCurrentView={(view) => {
          setCurrentView(view);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onOpenSubmitModal={() => setIsSubmitModalOpen(true)}
        hasDashboardReport={!!dashboardReport}
      />

      {/* Main View Area */}
      <main className="flex-grow pb-16">
        {currentView === 'catalog' && (
          <ProductCatalog
            searchQuery={searchQuery}
            onSelectProduct={handleSelectProduct}
          />
        )}

        {currentView === 'product_detail' && selectedProduct && (
          <ProductDetail
            product={selectedProduct}
            onBack={() => setCurrentView('catalog')}
            onSelectReviewer={handleSelectReviewer}
          />
        )}

        {currentView === 'reviewer_profile' && selectedReviewerId && (
          <ReviewerProfile
            reviewerId={selectedReviewerId}
            onBack={() => {
              if (selectedProduct) {
                setCurrentView('product_detail');
              } else {
                setCurrentView('catalog');
              }
            }}
          />
        )}

        {currentView === 'dashboard' && (
          <SubmitterDashboard
            reportData={dashboardReport}
            onBackToCatalog={() => setCurrentView('catalog')}
            onSelectProduct={handleSelectProduct}
            onSelectReviewer={handleSelectReviewer}
          />
        )}
      </main>

      {/* Drag-and-Drop Batch Submission Modal */}
      <SubmissionModal
        isOpen={isSubmitModalOpen}
        onClose={() => setIsSubmitModalOpen(false)}
        onSuccess={handleSubmissionSuccess}
      />

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950/60 py-6 px-6 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <p>Alastria Red T Reputation & Fraud Ledger • Enterprise Consortium Network</p>
          <p>Late Fusion AI Engine (GNN + DeBERTa) • EVM 1-Slot Hyper-Optimized Storage</p>
        </div>
      </footer>

    </div>
  );
}
