import os
import torch
import torch.nn.functional as F
from torch.nn import Linear, ModuleDict
from torch_geometric.nn import HGTConv

class HGTModel(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels, num_layers, num_heads, dropout, metadata):
        super(HGTModel, self).__init__()
        
        self.dropout = dropout
        
        # 1. Linear projections to map heterogeneous node features to the same hidden dimension
        self.node_lin = ModuleDict()
        # Note: In a dynamic scenario, you'd pass in dicts of input dims. 
        # For boilerplate, assuming input dimensions from build_graph.py:
        # reviewer: 6, product: 5, review: 5
        self.node_lin['reviewer'] = Linear(7, hidden_channels)
        self.node_lin['product'] = Linear(3, hidden_channels)
        self.node_lin['review'] = Linear(5, hidden_channels)
        
        # 2. Heterogeneous Graph Attention Layers
        self.convs = torch.nn.ModuleList()
        for _ in range(num_layers):
            conv = HGTConv(hidden_channels, hidden_channels, metadata, heads=num_heads)
            self.convs.append(conv)
        # 3. Multi-Task Classification Heads
        # Predict binary outcomes for Reviewer and Review nodes (Product acts as auxiliary bridge)
        self.reviewer_head = torch.nn.Sequential(
            Linear(hidden_channels, hidden_channels // 2),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.3),
            Linear(hidden_channels // 2, out_channels)
        )
        self.review_head = torch.nn.Sequential(
            Linear(hidden_channels, hidden_channels // 2),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.3),
            Linear(hidden_channels // 2, out_channels)
        )

    def forward(self, x_dict, edge_index_dict):
        # Apply initial linear projections and activation
        x_dict_projected = {}
        for node_type, x in x_dict.items():
            x_dict_projected[node_type] = F.relu(self.node_lin[node_type](x))
            
        # Message Passing
        x_dict = x_dict_projected
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            x_dict = {key: F.relu(x) for key, x in x_dict.items()}
            x_dict = {key: F.dropout(x, p=self.dropout, training=self.training) for key, x in x_dict.items()}
            
        # Classification Heads
        reviewer_out = self.reviewer_head(x_dict['reviewer'])
        review_out = self.review_head(x_dict['review'])
        
        return {
            'reviewer': reviewer_out,
            'review': review_out
        }
