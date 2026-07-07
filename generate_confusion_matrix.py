import torch
import json
import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix
from model import HGTModel

def plot_cm(cm, ax, title, class_names=['Honest (0)', 'Fake (1)'], cmap='Blues'):
    im = ax.imshow(cm, interpolation='nearest', cmap=cmap)
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    
    # Add colorbar
    cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=11)
    
    # Tick marks
    tick_marks = np.arange(len(class_names))
    ax.set_xticks(tick_marks)
    ax.set_xticklabels(class_names, fontsize=12, fontweight='bold')
    ax.set_yticks(tick_marks)
    ax.set_yticklabels(class_names, fontsize=12, fontweight='bold')
    
    # Labels
    ax.set_ylabel('True Ground Truth Label', fontsize=13, fontweight='bold')
    ax.set_xlabel('Predicted GNN Label', fontsize=13, fontweight='bold')
    
    # Text annotations inside boxes
    thresh = cm.max() / 2.
    total = np.sum(cm)
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            count = cm[i, j]
            pct = (count / total) * 100
            text_color = "white" if count > thresh else "black"
            ax.text(j, i, f"{count:,}\n({pct:.1f}%)",
                    ha="center", va="center",
                    color=text_color, fontsize=13, fontweight='bold')

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Generating Confusion Matrices using device: {device}")
    
    model_dir = "data"
    graph_path = os.path.join(model_dir, "hetero_graph.pt")
    weights_path = os.path.join(model_dir, "best_model.pth")
    thresholds_path = os.path.join(model_dir, "best_thresholds.json")
    
    # Load Data & Model
    data = torch.load(graph_path, map_location=device, weights_only=False)
    model = HGTModel(
        hidden_channels=64, 
        out_channels=1, 
        num_layers=2, 
        num_heads=4, 
        dropout=0.3,
        metadata=data.metadata()
    ).to(device)
    
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=False))
    model.eval()
    
    with open(thresholds_path, 'r') as f:
        thresholds = json.load(f)
    thresh_p = thresholds['product_threshold']
    thresh_r = thresholds['reviewer_threshold']
    thresh_rev = thresholds.get('review_threshold', 0.5)
    print(f"Optimal Thresholds -> Product: {thresh_p:.2f} | Reviewer: {thresh_r:.2f} | Review: {thresh_rev:.2f}\n")
    
    with torch.no_grad():
        out_dict = model(data.x_dict, data.edge_index_dict)
        prob_product = torch.sigmoid(out_dict['product'].squeeze(-1)).cpu().numpy()
        prob_reviewer = torch.sigmoid(out_dict['reviewer'].squeeze(-1)).cpu().numpy()
        prob_review = torch.sigmoid(out_dict['review'].squeeze(-1)).cpu().numpy()
        
        y_product = data['product'].y.cpu().numpy()
        y_reviewer = data['reviewer'].y.cpu().numpy()
        y_review = data['review'].y.cpu().numpy()
        
        p_test = data['product'].test_mask.cpu().numpy()
        r_test = data['reviewer'].test_mask.cpu().numpy()
        rev_test = data['review'].test_mask.cpu().numpy()
        
    # 1. Calculate Test Set Confusion Matrices
    pred_p_test = (prob_product[p_test] >= thresh_p).astype(int)
    cm_p_test = confusion_matrix(y_product[p_test], pred_p_test)
    
    pred_r_test = (prob_reviewer[r_test] >= thresh_r).astype(int)
    cm_r_test = confusion_matrix(y_reviewer[r_test], pred_r_test)
    
    pred_rev_test = (prob_review[rev_test] >= thresh_rev).astype(int)
    cm_rev_test = confusion_matrix(y_review[rev_test], pred_rev_test)
    
    # Plot Test Set Confusion Matrices
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    plot_cm(cm_p_test, axes[0], f"Product Head - Test Set ({p_test.sum()})", cmap='Purples')
    plot_cm(cm_r_test, axes[1], f"Reviewer Head - Test Set ({r_test.sum()})", cmap='Greens')
    plot_cm(cm_rev_test, axes[2], f"Review Head - Test Set ({rev_test.sum()})", cmap='Oranges')
    plt.tight_layout()
    test_cm_path = "gnn_test_set_confusion_matrices.png"
    plt.savefig(test_cm_path, dpi=300)
    plt.close()
    print(f"Saved Test Set Confusion Matrices to {test_cm_path}")
    
    # 2. Calculate Full Labeled Dataset Confusion Matrices
    pred_p_full = (prob_product >= thresh_p).astype(int)
    cm_p_full = confusion_matrix(y_product, pred_p_full)
    
    labeled_rev_mask = (y_reviewer != -1)
    pred_r_full = (prob_reviewer[labeled_rev_mask] >= thresh_r).astype(int)
    cm_r_full = confusion_matrix(y_reviewer[labeled_rev_mask], pred_r_full)
    
    labeled_review_mask = (y_review != -1)
    pred_rev_full = (prob_review[labeled_review_mask] >= thresh_rev).astype(int)
    cm_rev_full = confusion_matrix(y_review[labeled_review_mask], pred_rev_full)
    
    # Plot Full Dataset Confusion Matrices
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    plot_cm(cm_p_full, axes[0], f"Full Product Benchmark ({len(y_product)})", cmap='Purples')
    plot_cm(cm_r_full, axes[1], f"Full Reviewer Benchmark ({labeled_rev_mask.sum()})", cmap='Greens')
    plot_cm(cm_rev_full, axes[2], f"Full Review Benchmark ({labeled_review_mask.sum()})", cmap='Oranges')
    plt.tight_layout()
    full_cm_path = "gnn_full_dataset_confusion_matrices.png"
    plt.savefig(full_cm_path, dpi=300)
    plt.close()
    print(f"Saved Full Labeled Dataset Confusion Matrices to {full_cm_path}")

if __name__ == "__main__":
    main()
