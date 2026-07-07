import torch
from sklearn.metrics import average_precision_score, accuracy_score

@torch.no_grad()
def evaluate(model, data, mask_name='test_mask'):
    model.eval()
    out_dict = model(data.x_dict, data.edge_index_dict)
    
    metrics = {}
    
    for node_type in ['reviewer', 'product']:
        mask = data[node_type][mask_name]
        y_true = data[node_type].y[mask]
        out = out_dict[node_type][mask].squeeze()
            
        if len(y_true) == 0:
            metrics[node_type] = None
            continue
            
        y_true_np = y_true.cpu().numpy()
        probs = torch.sigmoid(out).cpu().numpy()
        preds = (probs > 0.5).astype(int)
        
        # Calculate TP, FP, FN
        tp = ((preds == 1) & (y_true_np == 1)).sum()
        fp = ((preds == 1) & (y_true_np == 0)).sum()
        fn = ((preds == 0) & (y_true_np == 1)).sum()
        tn = ((preds == 0) & (y_true_np == 0)).sum()
        
        # Precision and Recall
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        
        # F1 Formula from user
        if precision + recall > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0.0
            
        # AUCPR
        if len(set(y_true_np)) > 1:
            aucpr = average_precision_score(y_true_np, probs)
        else:
            aucpr = 0.0
            
        # Accuracy
        acc = accuracy_score(y_true_np, preds)
        
        metrics[node_type] = {
            'TP': tp,
            'FP': fp,
            'FN': fn,
            'TN': tn,
            'Accuracy': acc,
            'Precision': precision,
            'Recall': recall,
            'F1': f1,
            'AUCPR': aucpr
        }
        
    return metrics
