"""
Download NASA CMAPSS FD001 dataset.

The dataset is available from multiple sources:
1. NASA PCoE (official): https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
   -> Download "Turbofan Engine Degradation Simulation Data Set" (CMAPSSData.zip)

2. Kaggle: https://www.kaggle.com/datasets/behrad3d/nasa-cmaps
   -> Download via `kaggle datasets download behrad3d/nasa-cmaps`

3. PapersWithCode mirror (direct download):
   -> https://raw.githubusercontent.com/... (varies)

HOW TO USE:
    1. Download CMAPSSData.zip from one of the sources above
    2. Extract the zip file
    3. Copy train_FD001.txt, test_FD001.txt, RUL_FD001.txt into module-a/data/raw/

Or use the Kaggle CLI:
    pip install kaggle
    kaggle datasets download behrad3d/nasa-cmaps
    unzip nasa-cmaps.zip -d ./raw/
    cp raw/CMAPSSData/train_FD001.txt ./raw/
    cp raw/CMAPSSData/test_FD001.txt ./raw/
    cp raw/CMAPSSData/RUL_FD001.txt ./raw/
"""
import urllib.request
import io
import zipfile
import os
import sys

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(DATA_DIR, "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# Try multiple mirrors
MIRRORS = [
    # Mirror 1: GitHub raw mirror (community maintained)
    {
        "url": "https://raw.githubusercontent.com/HamidMoeinfar/cmapss-dataset/main/CMAPSSData.zip",
        "type": "zip",
    },
    # Mirror 2: Try Kaggle direct
    {
        "url": "https://storage.googleapis.com/kaggle-data-sets/358/805183/bundle/archive.zip",
        "type": "zip",
    },
]

def download_and_extract():
    for i, mirror in enumerate(MIRRORS):
        print(f"Trying mirror {i+1}: {mirror['url'][:60]}...")
        try:
            req = urllib.request.Request(
                mirror["url"],
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            
            if data[:2] == b'PK':  # ZIP magic bytes
                print(f"  Downloaded {len(data):,} bytes (valid ZIP)")
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    for name in zf.namelist():
                        # Extract FD001 files
                        base = os.path.basename(name)
                        if "FD001" in base and base.endswith('.txt'):
                            target = os.path.join(RAW_DIR, base)
                            # Handle nested paths (e.g., CMAPSSData/train_FD001.txt)
                            zf.extract(name, RAW_DIR)
                            # If extracted to subdir, move up
                            extracted = os.path.join(RAW_DIR, name)
                            if os.path.exists(extracted) and extracted != target:
                                import shutil
                                shutil.move(extracted, target)
                            print(f"    Extracted: {base}")
                
                # Verify
                for fname in ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]:
                    fp = os.path.join(RAW_DIR, fname)
                    if os.path.exists(fp):
                        print(f"  ✅ {fname}: {os.path.getsize(fp):,} bytes")
                    else:
                        print(f"  ⚠️ {fname}: not found in zip")
                return True
            else:
                print(f"  Not a ZIP (got HTML, {len(data)} bytes)")
        except Exception as e:
            print(f"  Failed: {e}")
    
    print("
⚠️ Automatic download failed. Please download manually:")
    print("   1. Go to: https://www.nasa.gov/intelligent-systems-division/")
    print("              discovery-and-systems-health/pcoe/pcoe-data-set-repository/")
    print("   2. Download CMAPSSData.zip")
    print("   3. Extract train_FD001.txt, test_FD001.txt, RUL_FD001.txt")
    print(f"   4. Place them in: {RAW_DIR}")
    return False


if __name__ == "__main__":
    # Check if already downloaded
    needed = ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]
    existing = all(os.path.exists(os.path.join(RAW_DIR, f)) for f in needed)
    if existing:
        print("✅ Dataset already downloaded.")
        for f in needed:
            fp = os.path.join(RAW_DIR, f)
            print(f"  {f}: {os.path.getsize(fp):,} bytes")
        sys.exit(0)
    
    print("Downloading NASA CMAPSS FD001 dataset...")
    download_and_extract()
