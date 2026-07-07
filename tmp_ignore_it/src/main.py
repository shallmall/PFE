import argparse
import torch
import os
import sys

# Ensure src is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.ingestion import load_and_construct_graph
from src.data.split import temporal_split
from src.models.gnn import create_hetero_gnn
from src.training.train import train_epoch
from src.training.evaluate import evaluate

def main():
    parser = argparse.ArgumentParser(description="GNN Fraud Detection Pipeline")
    parser.add_argument("--data_path", type=str, default="data/public_reviews_dataset_cleaned.csv", help="Path to the dataset CSV")
    parser.add_argument("--max_rows", type=int, default=10000, help="Max rows to read (set to 0 for all rows). Default is 10000 for faster testing.")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--hidden_channels", type=int, default=64, help="Hidden channels for GNN")
    
    args = parser.parse_args()
    
    max_rows = args.max_rows if args.max_rows > 0 else None
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # 1. Ingestion & Graph Construction
    print("\n--- Phase 1: Ingestion & Graph Construction ---")
    data, df, reviewer_mapping, product_mapping = load_and_construct_graph(args.data_path, max_rows=max_rows)
    
    # 2. Smart Data Split (Temporal)
    print("\n--- Phase 2: Smart Data Split ---")
    data = temporal_split(data, df, reviewer_mapping, product_mapping)
    data = data.to(device)
    
    # 3. Model Training
    print("\n--- Phase 3: Model Training ---")
    model = create_hetero_gnn(args.hidden_channels, 1, data.metadata()).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    for epoch in range(1, args.epochs + 1):
        loss, loss_rev, loss_prod = train_epoch(model, data, optimizer)
        if epoch % 5 == 0 or epoch == 1:
            print(f"Epoch {epoch:03d} | Loss: {loss:.4f} (Rev: {loss_rev:.4f}, Prod: {loss_prod:.4f})")
            
            # Validation
            val_metrics = evaluate(model, data, mask_name='val_mask')
            print("  Validation:")
            if val_metrics['reviewer']:
                print(f"    Reviewer AUCPR: {val_metrics['reviewer']['AUCPR']:.4f}")
            if val_metrics['product']:
                print(f"    Product AUCPR: {val_metrics['product']['AUCPR']:.4f}")

    # 4. Testing & F1 Evaluation
    print("\n--- Phase 4: Testing & F1 Evaluation ---")
    test_metrics = evaluate(model, data, mask_name='test_mask')
    
    for node_type, m in test_metrics.items():
        if m is None:
            print(f"No test data available for {node_type}.")
            continue
            
        print(f"\n======================================")
        print(f"   TERMINAL REPORT: {node_type.upper()}   ")
        print(f"======================================")
        print(f"Accuracy:  {m['Accuracy']:.4f}")
        print(f"Precision: {m['Precision']:.4f}")
        print(f"Recall:    {m['Recall']:.4f}")
        print(f"F1 Score:  {m['F1']:.4f}")
        print(f"AUCPR:     {m['AUCPR']:.4f}")
        print(f"--------------------------------------")
        print(f"True Positives (TP):  {m['TP']}")
        print(f"False Positives (FP): {m['FP']}")
        print(f"False Negatives (FN): {m['FN']}")
        print(f"True Negatives (TN):  {m['TN']}")
        print(f"======================================\n")

if __name__ == "__main__":
    main()
