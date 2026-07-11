import os
import torch

def install_pyg():
    # 1. Get the PyTorch version (e.g., '2.5.1')
    torch_version = torch.__version__.split('+')[0]
    
    # 2. Get the CUDA version (e.g., '12.1' -> 'cu121') or 'cpu'
    cuda_version = torch.version.cuda
    if cuda_version:
        cuda_str = f"cu{cuda_version.replace('.', '')}"
    else:
        cuda_str = "cpu"
        
    # 3. Construct the exact PyG index URL
    wheel_url = f"https://data.pyg.org/whl/torch-{torch_version}+{cuda_str}.html"
    
    # 4. Construct the uv pip install command
    install_cmd = f"uv pip install pyg_lib torch_scatter torch_sparse torch_cluster -f {wheel_url}"
    
    print(f"\n[+] Detected PyTorch: {torch_version}")
    print(f"[+] Detected Hardware: {cuda_str}")
    print(f"[+] Fetching PyTorch Geometric Extensions from: {wheel_url}\n")
    print(f"Running command: {install_cmd}\n")
    
    # 5. Execute the installation
    os.system(install_cmd)

if __name__ == "__main__":
    install_pyg()
