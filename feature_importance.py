import torch
import numpy as np
from sklearn.metrics import roc_auc_score
from model import HGTModel
import matplotlib.pyplot as plt

def evaluate_roc_auc(model, data, device):
    """Evaluates the model and returns the average ROC-AUC across Product, Reviewer, and Review heads on the Test Set."""
    model.eval()
    with torch.no_grad():
        out_dict = model(data.x_dict, data.edge_index_dict)
        
        prob_product = torch.sigmoid(out_dict['product'].squeeze(-1))
        prob_reviewer = torch.sigmoid(out_dict['reviewer'].squeeze(-1))
        prob_review = torch.sigmoid(out_dict['review'].squeeze(-1))
        
        p_test = data['product'].test_mask
        r_test = data['reviewer'].test_mask
        rev_test = data['review'].test_mask
        
        y_p_test = data['product'].y[p_test].cpu().numpy()
        y_r_test = data['reviewer'].y[r_test].cpu().numpy()
        y_rev_test = data['review'].y[rev_test].cpu().numpy()
        
        try:
            auc_p = roc_auc_score(y_p_test, prob_product[p_test].cpu().numpy())
            auc_r = roc_auc_score(y_r_test, prob_reviewer[r_test].cpu().numpy())
            auc_rev = roc_auc_score(y_rev_test, prob_review[rev_test].cpu().numpy())
            return (auc_p + auc_r + auc_rev) / 3.0
        except ValueError:
            return 0.0

def calculate_permutation_importance(graph_path="data/hetero_graph.pt", weights_path="data/best_model.pth"):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading data and model to {device}...")
    
    data = torch.load(graph_path)
    data = data.to(device)
    
    model = HGTModel(
        hidden_channels=64, 
        out_channels=1, 
        num_layers=2, 
        num_heads=4, 
        dropout=0.3,
        metadata=data.metadata()
    ).to(device)
    
    # Load the best weights
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    
    # Calculate baseline
    baseline_auc = evaluate_roc_auc(model, data, device)
    print(f"Baseline Average Test ROC-AUC: {baseline_auc:.4f}\n")
    
    # Define the exact features we engineered in build_graph.py in order
    feature_names = {
        'reviewer': [
            'review_volume', 'mean_rating_given', 'rating_variance', 
            'helpfulness_ratio', 'media_propensity', 'max_daily_velocity',
            'avg_target_product_bimodal_index'
        ],
        'product': [
            'total_review_weight', 'bimodal_index', 'arrival_velocity'
        ],
        'review': [
            'review_rating', 'rating_dev_from_mean', 'number_of_helpful', 
            'number_of_photos'
        ]
    }
    
    importances = []
    
    print("Calculating Permutation Feature Importance...")
    # Iterate through every node type and every feature
    for node_type, names in feature_names.items():
        original_tensor = data[node_type].x.clone()
        
        for feature_idx, feature_name in enumerate(names):
            # Clone to restore later
            data[node_type].x = original_tensor.clone()
            
            # Permute (shuffle) the specific feature column to destroy its signal
            perm_indices = torch.randperm(data[node_type].x.size(0))
            data[node_type].x[:, feature_idx] = data[node_type].x[perm_indices, feature_idx]
            
            # Evaluate performance drop
            permuted_auc = evaluate_roc_auc(model, data, device)
            drop = baseline_auc - permuted_auc
            
            # Record
            importances.append((f"{node_type}::{feature_name}", drop))
            print(f"  {node_type}::{feature_name} -> Drop: {drop:.4f}")
            
        # Restore completely after node type is done
        data[node_type].x = original_tensor
        
    # Sort descending by importance (biggest drop first)
    importances.sort(key=lambda x: x[1], reverse=True)
    
    print("\n--- Feature Importance Ranking ---")
    for rank, (name, drop) in enumerate(importances, 1):
        print(f"{rank}. {name} (ROC-AUC drop: {drop:.4f})")
        
    # Plotting
    names = [x[0] for x in importances]
    drops = [x[1] for x in importances]
    
    plt.figure(figsize=(12, 8))
    plt.barh(names[::-1], drops[::-1], color='coral')
    plt.xlabel('Drop in Average Test ROC-AUC (Higher = More Important)')
    plt.title('Permutation Feature Importance for HGTModel')
    plt.tight_layout()
    plt.savefig('feature_importance.png')
    print("\nBar chart saved to feature_importance.png")

if __name__ == "__main__":
    calculate_permutation_importance()
