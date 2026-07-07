import torch
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, to_hetero

class GNN(torch.nn.Module):
    def __init__(self, hidden_channels, out_channels):
        super().__init__()
        self.conv1 = SAGEConv((-1, -1), hidden_channels)
        self.conv2 = SAGEConv((-1, -1), hidden_channels)
        self.lin = torch.nn.Linear(hidden_channels, out_channels)
        self.dropout = torch.nn.Dropout(p=0.5)

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = x.relu()
        x = self.dropout(x)
        x = self.conv2(x, edge_index)
        x = x.relu()
        return self.lin(x)

def create_hetero_gnn(hidden_channels, out_channels, metadata):
    model = GNN(hidden_channels, out_channels)
    # Convert homogeneous GNN to heterogeneous GNN using 'mean' aggregation
    model = to_hetero(model, metadata, aggr='mean')
    return model
