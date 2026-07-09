import os
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import numpy as np
import copy
from model import HGTModel
import json
from torch_geometric.loader import NeighborLoader
from tqdm import tqdm



class BinaryFocalLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0, reduction='mean', pos_weight=None):
        super(BinaryFocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        self.bce = nn.BCEWithLogitsLoss(reduction='none', pos_weight=pos_weight)

    def forward(self, inputs, targets):
        bce_loss = self.bce(inputs, targets.float())
        pt = torch.exp(-bce_loss)
        focal_loss = self.alpha * (1 - pt)**self.gamma * bce_loss
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss

def find_best_threshold(y_true, y_pred_prob):
    best_thresh = 0.5
    best_f1 = 0.0
    for thresh in np.arange(0.01, 1.0, 0.005):
        y_pred = (y_pred_prob >= thresh).astype(int)
        macro_f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)
        if macro_f1 > best_f1:
            best_f1 = macro_f1
            best_thresh = thresh
    return best_thresh

def calculate_metrics(y_true, y_pred_prob, threshold=0.5):
    if len(np.unique(y_true)) > 1:
        roc_auc = roc_auc_score(y_true, y_pred_prob)
    else:
        roc_auc = float('nan')
        
    y_pred = (y_pred_prob >= threshold).astype(int)
    acc = accuracy_score(y_true, y_pred)
    prec_fake = precision_score(y_true, y_pred, pos_label=1, zero_division=0)
    rec_fake = recall_score(y_true, y_pred, pos_label=1, zero_division=0)
    f1_fake = f1_score(y_true, y_pred, pos_label=1, zero_division=0)
    prec_real = precision_score(y_true, y_pred, pos_label=0, zero_division=0)
    rec_real = recall_score(y_true, y_pred, pos_label=0, zero_division=0)
    f1_real = f1_score(y_true, y_pred, pos_label=0, zero_division=0)
    f1_mac = f1_score(y_true, y_pred, average='macro', zero_division=0)
    
    return {
        'acc': acc, 'roc_auc': roc_auc, 'f1_macro': f1_mac,
        'prec_fake': prec_fake, 'rec_fake': rec_fake, 'f1_fake': f1_fake,
        'prec_real': prec_real, 'rec_real': rec_real, 'f1_real': f1_real
    }

def print_metrics(metrics, title):
    print(f"--- {title} ---")
    print(f"Accuracy: {metrics['acc']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f} | F1-Macro: {metrics['f1_macro']:.4f}")
    print(f"  [Real/0] Precision: {metrics['prec_real']:.4f} | Recall: {metrics['rec_real']:.4f} | F1: {metrics['f1_real']:.4f}")
    print(f"  [Fake/1] Precision: {metrics['prec_fake']:.4f} | Recall: {metrics['rec_fake']:.4f} | F1: {metrics['f1_fake']:.4f}")
    print("-" * 40)

def train(graph_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/hetero_graph.pt")):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    data = torch.load(graph_path)
    
    # NeighborLoaders for Train, Val, Test (Time-Aware!)
    # Batch size 1024, sample 10 neighbors in hop 1, 10 in hop 2.
    print("Setting up strict time-aware NeighborLoaders (Zero Leakage)...")
    loader_r_train = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].train_mask), time_attr='max_time', batch_size=1024, shuffle=True, num_workers=2)
    loader_rev_train = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('review', data['review'].train_mask), time_attr='time', batch_size=1024, shuffle=True, num_workers=2)
    
    loader_r_val = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].val_mask), time_attr='max_time', batch_size=2048, shuffle=False, num_workers=2)
    loader_rev_val = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('review', data['review'].val_mask), time_attr='time', batch_size=2048, shuffle=False, num_workers=2)

    loader_r_test = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].test_mask), time_attr='max_time', batch_size=2048, shuffle=False, num_workers=2)
    loader_rev_test = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('review', data['review'].test_mask), time_attr='time', batch_size=2048, shuffle=False, num_workers=2)

    # Note: model should be on device, but we pass data sequentially.
    model = HGTModel(hidden_channels=64, out_channels=1, num_layers=2, num_heads=4, dropout=0.3, metadata=data.metadata()).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)
    
    # Weights calculation
    r_train = data['reviewer'].train_mask
    rev_train = data['review'].train_mask
    y_reviewer = data['reviewer'].y
    y_review = data['review'].y
    num_pos_r = y_reviewer[r_train].sum().item()
    num_neg_r = len(y_reviewer[r_train]) - num_pos_r
    pos_weight_r = torch.tensor([num_neg_r / max(1, num_pos_r)], device=device)
    
    num_pos_rev = y_review[rev_train].sum().item()
    num_neg_rev = len(y_review[rev_train]) - num_pos_rev
    pos_weight_rev = torch.tensor([num_neg_rev / max(1, num_pos_rev)], device=device)
    
    print(f"Computed Class Weights - Reviewer: {pos_weight_r.item():.2f}, Review: {pos_weight_rev.item():.2f}")
    
    criterion_reviewer = BinaryFocalLoss(alpha=0.25, gamma=2.0, pos_weight=None)
    criterion_review = BinaryFocalLoss(alpha=0.25, gamma=2.0, pos_weight=None)
    
    patience = 5  # Lower patience since epochs take longer now
    min_delta = 1e-4
    best_val_loss = float('inf')
    epochs_no_improve = 0
    best_model_weights = None
    num_epochs = 100
    
    for epoch in range(num_epochs):
        model.train()
        total_loss_r = 0
        total_loss_rev = 0
        
        # Train Reviewer nodes
        for batch in loader_r_train:
            batch = batch.to(device)
            optimizer.zero_grad()
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            
            out_r = out_dict['reviewer'][:batch['reviewer'].batch_size].squeeze(-1)
            y_r = batch['reviewer'].y[:batch['reviewer'].batch_size]
            
            loss = criterion_reviewer(out_r, y_r)
            loss.backward()
            optimizer.step()
            total_loss_r += loss.item() * batch['reviewer'].batch_size
            
        # Train Review nodes
        for batch in loader_rev_train:
            batch = batch.to(device)
            optimizer.zero_grad()
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            
            out_rev = out_dict['review'][:batch['review'].batch_size].squeeze(-1)
            y_rev = batch['review'].y[:batch['review'].batch_size]
            
            loss = criterion_review(out_rev, y_rev)
            loss.backward()
            optimizer.step()
            total_loss_rev += loss.item() * batch['review'].batch_size
            
        avg_train_loss = (total_loss_r + total_loss_rev) / (y_reviewer[r_train].size(0) + y_review[rev_train].size(0))
        
        # Validation
        model.eval()
        val_loss_r = 0
        val_loss_rev = 0
        all_y_r = []
        all_prob_r = []
        all_y_rev = []
        all_prob_rev = []
        
        with torch.no_grad():
            for batch in loader_r_val:
                batch = batch.to(device)
                out_dict = model(batch.x_dict, batch.edge_index_dict)
                out_r = out_dict['reviewer'][:batch['reviewer'].batch_size].squeeze(-1)
                y_r = batch['reviewer'].y[:batch['reviewer'].batch_size]
                
                loss = criterion_reviewer(out_r, y_r)
                val_loss_r += loss.item() * batch['reviewer'].batch_size
                all_y_r.extend(y_r.cpu().numpy())
                all_prob_r.extend(torch.sigmoid(out_r).cpu().numpy())
                
            for batch in loader_rev_val:
                batch = batch.to(device)
                out_dict = model(batch.x_dict, batch.edge_index_dict)
                out_rev = out_dict['review'][:batch['review'].batch_size].squeeze(-1)
                y_rev = batch['review'].y[:batch['review'].batch_size]
                
                loss = criterion_review(out_rev, y_rev)
                val_loss_rev += loss.item() * batch['review'].batch_size
                all_y_rev.extend(y_rev.cpu().numpy())
                all_prob_rev.extend(torch.sigmoid(out_rev).cpu().numpy())
                
        avg_val_loss = (val_loss_r + val_loss_rev) / (len(all_y_r) + len(all_y_rev))
        val_metrics_r = calculate_metrics(np.array(all_y_r), np.array(all_prob_r))
        val_metrics_rev = calculate_metrics(np.array(all_y_rev), np.array(all_prob_rev))
        
        print(f"Epoch {epoch:03d} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val ROC-AUC (Rev): {val_metrics_r['roc_auc']:.4f} | Val ROC-AUC (Review): {val_metrics_rev['roc_auc']:.4f}", flush=True)
        
        if avg_val_loss < best_val_loss - min_delta:
            best_val_loss = avg_val_loss
            epochs_no_improve = 0
            best_model_weights = copy.deepcopy(model.state_dict())
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stopping triggered at epoch {epoch}")
                break
                
    # Evaluation on Test Set
    print("\n--- Training Complete. Evaluating on Test Set ---")
    model.load_state_dict(best_model_weights)
    model.eval()
    
    all_y_r_test, all_prob_r_test = [], []
    all_y_rev_test, all_prob_rev_test = [], []
    
    # Re-gather validation predictions for threshold tuning
    all_y_r_val, all_prob_r_val = [], []
    all_y_rev_val, all_prob_rev_val = [], []
    
    with torch.no_grad():
        for batch in loader_r_val:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_r = out_dict['reviewer'][:batch['reviewer'].batch_size].squeeze(-1)
            y_r = batch['reviewer'].y[:batch['reviewer'].batch_size]
            all_y_r_val.extend(y_r.cpu().numpy())
            all_prob_r_val.extend(torch.sigmoid(out_r).cpu().numpy())
            
        for batch in loader_rev_val:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_rev = out_dict['review'][:batch['review'].batch_size].squeeze(-1)
            y_rev = batch['review'].y[:batch['review'].batch_size]
            all_y_rev_val.extend(y_rev.cpu().numpy())
            all_prob_rev_val.extend(torch.sigmoid(out_rev).cpu().numpy())
            
        for batch in loader_r_test:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_r = out_dict['reviewer'][:batch['reviewer'].batch_size].squeeze(-1)
            y_r = batch['reviewer'].y[:batch['reviewer'].batch_size]
            all_y_r_test.extend(y_r.cpu().numpy())
            all_prob_r_test.extend(torch.sigmoid(out_r).cpu().numpy())
            
        for batch in loader_rev_test:
            batch = batch.to(device)
            out_dict = model(batch.x_dict, batch.edge_index_dict)
            out_rev = out_dict['review'][:batch['review'].batch_size].squeeze(-1)
            y_rev = batch['review'].y[:batch['review'].batch_size]
            all_y_rev_test.extend(y_rev.cpu().numpy())
            all_prob_rev_test.extend(torch.sigmoid(out_rev).cpu().numpy())
            
    best_thresh_r = find_best_threshold(np.array(all_y_r_val), np.array(all_prob_r_val))
    best_thresh_rev = find_best_threshold(np.array(all_y_rev_val), np.array(all_prob_rev_val))
    
    print(f"Optimal Accuracy Thresholds (Tuned on Val) -> Reviewer: {best_thresh_r:.2f}, Review: {best_thresh_rev:.2f}\n")
    model_save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
    os.makedirs(model_save_dir, exist_ok=True)
    with open(os.path.join(model_save_dir, "best_thresholds.json"), 'w') as f:
        json.dump({'reviewer_threshold': float(best_thresh_r), 'review_threshold': float(best_thresh_rev)}, f, indent=4)
    with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/best_thresholds.json"), 'w') as f:
        json.dump({'reviewer_threshold': float(best_thresh_r), 'review_threshold': float(best_thresh_rev)}, f, indent=4)
        
    metrics_r_test = calculate_metrics(np.array(all_y_r_test), np.array(all_prob_r_test), threshold=best_thresh_r)
    metrics_rev_test = calculate_metrics(np.array(all_y_rev_test), np.array(all_prob_rev_test), threshold=best_thresh_rev)
    
    print_metrics(metrics_r_test, "Reviewer Head")
    print_metrics(metrics_rev_test, "Review Head")
    
    metrics_export = {
        'reviewer_head': {k: float(v) for k, v in metrics_r_test.items()},
        'review_head': {k: float(v) for k, v in metrics_rev_test.items()}
    }
    metrics_path_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/hgt_model_metrics.json")
    metrics_path_local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hgt_model_metrics.json")
    with open(metrics_path_data, 'w') as f:
        json.dump(metrics_export, f, indent=4)
    with open(metrics_path_local, 'w') as f:
        json.dump(metrics_export, f, indent=4)
    print(f"\nMetrics successfully saved to data/hgt_model_metrics.json and HGT_Heterogeneous_Graph_Model/hgt_model_metrics.json")
    
    model_save_path = os.path.join(model_save_dir, "best_model.pth")
    data_model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/best_model.pth")
    torch.save(best_model_weights, model_save_path)
    torch.save(best_model_weights, data_model_path)
    print(f"Best model weights synchronized and saved to:\n  -> {model_save_path}\n  -> {data_model_path}")

if __name__ == "__main__":
    train()
