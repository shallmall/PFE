import torch
import torch.nn.functional as F

def train_epoch(model, data, optimizer):
    model.train()
    optimizer.zero_grad()
    
    out_dict = model(data.x_dict, data.edge_index_dict)
    
    # --- Reviewer Loss ---
    rev_mask = data['reviewer'].train_mask
    rev_y = data['reviewer'].y[rev_mask]
    rev_out = out_dict['reviewer'][rev_mask].squeeze()
    
    loss_rev = torch.tensor(0.0, device=rev_y.device)
    if len(rev_y) > 0:
        # Calculate pos_weight for reviewers
        num_pos_rev = (rev_y == 1).sum().float()
        num_neg_rev = (rev_y == 0).sum().float()
        if num_neg_rev == 0:
            rev_pos_weight = torch.tensor(1.0, device=rev_y.device)
        else:
            rev_pos_weight = num_neg_rev / torch.clamp(num_pos_rev, min=1.0)
        
        loss_rev = F.binary_cross_entropy_with_logits(
            rev_out, 
            rev_y.float(), 
            pos_weight=rev_pos_weight
        )
        
    # --- Product Loss ---
    prod_mask = data['product'].train_mask
    prod_y = data['product'].y[prod_mask]
    prod_out = out_dict['product'][prod_mask].squeeze()
    
    loss_prod = torch.tensor(0.0, device=prod_y.device)
    if len(prod_y) > 0:
        # Calculate pos_weight for products
        num_pos_prod = (prod_y == 1).sum().float()
        num_neg_prod = (prod_y == 0).sum().float()
        if num_neg_prod == 0:
            prod_pos_weight = torch.tensor(1.0, device=prod_y.device)
        else:
            prod_pos_weight = num_neg_prod / torch.clamp(num_pos_prod, min=1.0)
        
        loss_prod = F.binary_cross_entropy_with_logits(
            prod_out, 
            prod_y.float(), 
            pos_weight=prod_pos_weight
        )
    
    # Total loss
    loss = loss_rev + loss_prod
    
    if loss.requires_grad:
        loss.backward()
        optimizer.step()
    
    return loss.item(), loss_rev.item(), loss_prod.item()
