import pandas as pd
import numpy as np
import torch
from torch_geometric.data import HeteroData
import torch_geometric.transforms as T
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

def load_and_construct_graph(csv_path: str, max_rows: int = None) -> tuple[HeteroData, pd.DataFrame]:
    print(f"Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    
    if max_rows is not None and max_rows > 0 and len(df) > max_rows:
        print(f"Sampling {max_rows} rows from the dataset...")
        df = df.sample(n=max_rows, random_state=42).reset_index(drop=True)
        
    # Handle missing text
    df['review_text'] = df['review_text'].fillna("")
    
    # Mappings from ID to index
    reviewer_ids = df['reviewer_id'].unique()
    reviewer_mapping = {id: i for i, id in enumerate(reviewer_ids)}
    
    product_ids = df['asin'].unique()
    product_mapping = {id: i for i, id in enumerate(product_ids)}
    
    # Target values (Labels)
    # Reviewer Labels: fake=1, else=0
    reviewer_y = np.zeros(len(reviewer_ids), dtype=np.int64)
    reviewer_df = df.groupby('reviewer_id').first()
    for reviewer_id, row in reviewer_df.iterrows():
        idx = reviewer_mapping[reviewer_id]
        if row.get('reviewer_classified_fake', False):
            reviewer_y[idx] = 1
            
    # Product Labels: fake=1, legit=0
    product_y = np.zeros(len(product_ids), dtype=np.int64)
    product_df = df.groupby('asin').first()
    for asin, row in product_df.iterrows():
        idx = product_mapping[asin]
        if row.get('fake_review_product', False) == True:
            product_y[idx] = 1
            
    print("Computing text embeddings using TF-IDF...")
    vectorizer = TfidfVectorizer(max_features=128, stop_words='english')
    text_embeddings = vectorizer.fit_transform(df['review_text']).toarray()
    
    # Process edges and features
    print("Processing edges and aggregating features...")
    edge_index_reviewer_product = []
    
    feat_dim = text_embeddings.shape[1] + 2 # +2 for rating, timestamp
    reviewer_features_sum = np.zeros((len(reviewer_ids), feat_dim))
    reviewer_features_count = np.zeros(len(reviewer_ids))
    
    product_features_sum = np.zeros((len(product_ids), feat_dim))
    product_features_count = np.zeros(len(product_ids))
    
    # Normalize timestamp and rating
    df['review_date'] = pd.to_datetime(df['review_date'])
    df['timestamp'] = df['review_date'].astype('int64') // 10**9
    
    scaler = StandardScaler()
    df[['review_rating', 'timestamp']] = scaler.fit_transform(df[['review_rating', 'timestamp']])
    
    # Collect edge features and graph
    # Optimizing the loop using numpy
    r_indices = np.array([reviewer_mapping[r] for r in df['reviewer_id']])
    p_indices = np.array([product_mapping[p] for p in df['asin']])
    ratings = df['review_rating'].values
    timestamps = df['timestamp'].values
    
    edge_index_reviewer_product = np.vstack([r_indices, p_indices])
    
    for i in range(len(df)):
        feat = np.concatenate([text_embeddings[i], [ratings[i], timestamps[i]]])
        r_idx = r_indices[i]
        p_idx = p_indices[i]
        
        reviewer_features_sum[r_idx] += feat
        reviewer_features_count[r_idx] += 1
        
        product_features_sum[p_idx] += feat
        product_features_count[p_idx] += 1
        
    # Average the features
    reviewer_features = reviewer_features_sum / np.maximum(reviewer_features_count[:, None], 1)
    product_features = product_features_sum / np.maximum(product_features_count[:, None], 1)
    
    # Construct HeteroData
    data = HeteroData()
    
    data['reviewer'].x = torch.tensor(reviewer_features, dtype=torch.float)
    data['reviewer'].y = torch.tensor(reviewer_y, dtype=torch.float) # float for BCEWithLogitsLoss
    
    data['product'].x = torch.tensor(product_features, dtype=torch.float)
    data['product'].y = torch.tensor(product_y, dtype=torch.float) # float for BCEWithLogitsLoss
    
    data['reviewer', 'reviews', 'product'].edge_index = torch.tensor(edge_index_reviewer_product, dtype=torch.long)
    
    # Add reverse edges for undirected message passing
    data = T.ToUndirected()(data)
    
    print("Graph construction complete!")
    print(data)
    return data, df, reviewer_mapping, product_mapping
