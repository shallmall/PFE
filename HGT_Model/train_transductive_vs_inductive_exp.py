import os
import sys
import copy
import json
import torch
import numpy as np
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, precision_recall_curve, auc
from torch_geometric.loader import NeighborLoader

# Configure stdout encoding for Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import model and loss from local directory
from model import HGTModel
from train import BinaryFocalLoss, find_best_threshold, calculate_metrics, print_metrics

def run_experiment(mode="transductive", graph_path=None):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n=======================================================================")
    print(f"  STARTING EXPERIMENT: {mode.upper()} LEARNING MODE")
    print(f"=======================================================================")
    
    data = torch.load(graph_path)
    
    if mode == "inductive":
        print("-> INDUCTIVE MODE: Masking out Val & Test nodes from training graph structure...")
        print("-> Note: Unlabeled background nodes (y == -1) remain present in all splits!")
        train_data = copy.deepcopy(data)
        
        # Identify allowed nodes for training (Train nodes + Unlabeled background nodes)
        allowed_reviewer = ~(data['reviewer'].val_mask | data['reviewer'].test_mask)
        allowed_review = ~(data['review'].val_mask | data['review'].test_mask)
        allowed_product = ~(data['product'].val_mask | data['product'].test_mask)
        
        # Filter edge_index for ('reviewer', 'authored', 'review')
        edge_idx_1 = train_data['reviewer', 'authored', 'review'].edge_index
        mask_1 = allowed_reviewer[edge_idx_1[0]] & allowed_review[edge_idx_1[1]]
        train_data['reviewer', 'authored', 'review'].edge_index = edge_idx_1[:, mask_1]
        
        # Filter edge_index for ('review', 'targeted', 'product')
        edge_idx_2 = train_data['review', 'targeted', 'product'].edge_index
        mask_2 = allowed_review[edge_idx_2[0]] & allowed_product[edge_idx_2[1]]
        train_data['review', 'targeted', 'product'].edge_index = edge_idx_2[:, mask_2]
        
        # If undirected reverse edges exist:
        if ('review', 'rev_authored', 'reviewer') in train_data.edge_types:
            edge_idx_3 = train_data['review', 'rev_authored', 'reviewer'].edge_index
            mask_3 = allowed_review[edge_idx_3[0]] & allowed_reviewer[edge_idx_3[1]]
            train_data['review', 'rev_authored', 'reviewer'].edge_index = edge_idx_3[:, mask_3]
            
        if ('product', 'rev_targeted', 'review') in train_data.edge_types:
            edge_idx_4 = train_data['product', 'rev_targeted', 'review'].edge_index
            mask_4 = allowed_product[edge_idx_4[0]] & allowed_review[edge_idx_4[1]]
            train_data['product', 'rev_targeted', 'review'].edge_index = edge_idx_4[:, mask_4]
            
        train_graph_source = train_data
    else:
        print("-> TRANSDUCTIVE MODE: Using unified graph structure with time-aware sampling...")
        print("-> Note: Unlabeled background nodes (y == -1) remain present in all splits!")
        train_graph_source = data

    # Time-Aware NeighborLoaders (Zero Leakage maintained!)
    loader_r_train = NeighborLoader(train_graph_source, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].train_mask), time_attr='max_time', batch_size=1024, shuffle=True, num_workers=2)
    loader_rev_train = NeighborLoader(train_graph_source, num_neighbors=[10, 10], input_nodes=('review', data['review'].train_mask), time_attr='time', batch_size=1024, shuffle=True, num_workers=2)
    
    loader_r_val = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].val_mask), time_attr='max_time', batch_size=2048, shuffle=False, num_workers=2)
    loader_rev_val = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('review', data['review'].val_mask), time_attr='time', batch_size=2048, shuffle=False, num_workers=2)

    loader_r_test = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('reviewer', data['reviewer'].test_mask), time_attr='max_time', batch_size=2048, shuffle=False, num_workers=2)
    loader_rev_test = NeighborLoader(data, num_neighbors=[10, 10], input_nodes=('review', data['review'].test_mask), time_attr='time', batch_size=2048, shuffle=False, num_workers=2)

    model = HGTModel(hidden_channels=64, out_channels=1, num_layers=2, num_heads=4, dropout=0.3, metadata=data.metadata()).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005, weight_decay=5e-4)
    
    r_train = data['reviewer'].train_mask
    rev_train = data['review'].train_mask
    y_reviewer = data['reviewer'].y
    y_review = data['review'].y
    
    criterion_reviewer = BinaryFocalLoss(alpha=0.25, gamma=2.0, pos_weight=None)
    criterion_review = BinaryFocalLoss(alpha=0.25, gamma=2.0, pos_weight=None)
    
    patience = 5
    min_delta = 1e-4
    best_val_loss = float('inf')
    epochs_no_improve = 0
    best_model_weights = None
    num_epochs = 100
    
    for epoch in range(num_epochs):
        model.train()
        total_loss_r = 0
        total_loss_rev = 0
        
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
        
        model.eval()
        val_loss_r, val_loss_rev = 0, 0
        all_y_r, all_prob_r = [], []
        all_y_rev, all_prob_rev = [], []
        
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
        
        print(f"[{mode.upper()}] Epoch {epoch:03d} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val PR-AUC (Rev): {val_metrics_r['pr_auc']:.4f} | Val PR-AUC (Review): {val_metrics_rev['pr_auc']:.4f}", flush=True)
        
        if avg_val_loss < best_val_loss - min_delta:
            best_val_loss = avg_val_loss
            epochs_no_improve = 0
            best_model_weights = copy.deepcopy(model.state_dict())
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                print(f"Early stopping triggered at epoch {epoch}")
                break
                
    print(f"\n--- {mode.upper()} Training Complete. Evaluating on Test Set ---")
    model.load_state_dict(best_model_weights)
    model.eval()
    
    all_y_r_val, all_prob_r_val = [], []
    all_y_rev_val, all_prob_rev_val = [], []
    all_y_r_test, all_prob_r_test = [], []
    all_y_rev_test, all_prob_rev_test = [], []
    
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
    
    metrics_r_test = calculate_metrics(np.array(all_y_r_test), np.array(all_prob_r_test), threshold=best_thresh_r)
    metrics_rev_test = calculate_metrics(np.array(all_y_rev_test), np.array(all_prob_rev_test), threshold=best_thresh_rev)
    
    print_metrics(metrics_r_test, f"{mode.upper()} - Reviewer Head")
    print_metrics(metrics_rev_test, f"{mode.upper()} - Review Head")
    
    return metrics_r_test, metrics_rev_test

def main():
    graph_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/hetero_graph.pt")
    
    print("═" * 80)
    print("  ABLATION EXPERIMENT: TRANSDUCTIVE vs INDUCTIVE LEARNING IN HGT")
    print("═" * 80)
    
    # 1. Run Transductive Baseline
    metrics_r_trans, metrics_rev_trans = run_experiment("transductive", graph_path)
    
    # 2. Run Inductive Control
    metrics_r_ind, metrics_rev_ind = run_experiment("inductive", graph_path)
    
    # Summary Table
    print("\n" + "═" * 80)
    print("                      FINAL EXPERIMENT SUMMARY COMPARISON")
    print("═" * 80)
    print(f"{'Metric':<25} | {'Transductive (Baseline)':<25} | {'Inductive (Control)':<25}")
    print("-" * 80)
    print(f"{'Reviewer ROC-AUC':<25} | {metrics_r_trans['roc_auc']:<25.4f} | {metrics_r_ind['roc_auc']:<25.4f}")
    print(f"{'Reviewer F1-Macro':<25} | {metrics_r_trans['f1_macro']:<25.4f} | {metrics_r_ind['f1_macro']:<25.4f}")
    print(f"{'Reviewer Acc':<25} | {metrics_r_trans['acc']:<25.4f} | {metrics_r_ind['acc']:<25.4f}")
    print("-" * 80)
    print(f"{'Review ROC-AUC':<25} | {metrics_rev_trans['roc_auc']:<25.4f} | {metrics_rev_ind['roc_auc']:<25.4f}")
    print(f"{'Review F1-Macro':<25} | {metrics_rev_trans['f1_macro']:<25.4f} | {metrics_rev_ind['f1_macro']:<25.4f}")
    print(f"{'Review Acc':<25} | {metrics_rev_trans['acc']:<25.4f} | {metrics_rev_ind['acc']:<25.4f}")
    print("═" * 80)

if __name__ == "__main__":
    main()
