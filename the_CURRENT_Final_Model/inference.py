import torch
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from model import HGTModel
from train import calculate_metrics, print_metrics
"""
for this model we changed the head from simple one neuron to multipple layers neurons

"""
def evaluate_model(model_dir="the_CURRENT_Final_Model"):
    """
    Loads the saved model and thresholds from the specified directory
    and runs evaluation on the Test Set.
    """
    graph_path = os.path.join(model_dir, "hetero_graph.pt")
    weights_path = os.path.join(model_dir, "best_model.pth")
    thresholds_path = os.path.join(model_dir, "best_thresholds.json")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading data and model to {device}...")
    
    # 1. Load Data
    data = torch.load(graph_path, map_location=device)
    
    # 2. Re-instantiate the Architecture
    model = HGTModel(
        hidden_channels=64, 
        out_channels=1, 
        num_layers=2, 
        num_heads=4, 
        dropout=0.3,
        metadata=data.metadata()
    ).to(device)
    
    # 3. Load Saved Weights
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    model.eval()
    
    # 4. Load Saved Thresholds
    with open(thresholds_path, 'r') as f:
        thresholds = json.load(f)
    
    thresh_p = thresholds['product_threshold']
    thresh_r = thresholds['reviewer_threshold']
    print(f"Loaded Thresholds - Product: {thresh_p:.2f}, Reviewer: {thresh_r:.2f}\n")
    
    # 5. Run Inference
    with torch.no_grad():
        out_dict = model(data.x_dict, data.edge_index_dict)
        
        # Convert raw logits to probabilities
        prob_product = torch.sigmoid(out_dict['product'].squeeze(-1))
        prob_reviewer = torch.sigmoid(out_dict['reviewer'].squeeze(-1))
        
        # Get Test Masks
        p_test = data['product'].test_mask
        r_test = data['reviewer'].test_mask
        
        # Retrieve Targets
        y_p_test = data['product'].y[p_test].cpu().numpy()
        y_r_test = data['reviewer'].y[r_test].cpu().numpy()
        
        # Calculate Metrics
        metrics_product = calculate_metrics(y_p_test, prob_product[p_test].cpu().numpy(), threshold=thresh_p)
        metrics_reviewer = calculate_metrics(y_r_test, prob_reviewer[r_test].cpu().numpy(), threshold=thresh_r)
        
        # Print Results
        print_metrics(metrics_product, "Product Head (Test Set)")
        print_metrics(metrics_reviewer, "Reviewer Head (Test Set)")
        
        # Save to file
        metrics_file = os.path.join(model_dir, "final_model_metrics.txt")
        with open(metrics_file, 'w') as f:
            def write_m(m, title):
                f.write(f"--- {title} ---\n")
                f.write(f"Accuracy: {m['acc']:.4f} | ROC-AUC: {m['roc_auc']:.4f} | PR-AUC: {m['pr_auc']:.4f} | F1-Macro: {m['f1_macro']:.4f}\n")
                f.write(f"  [Real/0] Precision: {m['prec_real']:.4f} | Recall: {m['rec_real']:.4f} | F1: {m['f1_real']:.4f}\n")
                f.write(f"  [Fake/1] Precision: {m['prec_fake']:.4f} | Recall: {m['rec_fake']:.4f} | F1: {m['f1_fake']:.4f}\n")
                f.write("-" * 40 + "\n")
            
            write_m(metrics_product, "Product Head (Test Set)")
            write_m(metrics_reviewer, "Reviewer Head (Test Set)")
            print(f"Metrics successfully saved to {metrics_file}")
        
    return metrics_product, metrics_reviewer

if __name__ == "__main__":
    evaluate_model()
