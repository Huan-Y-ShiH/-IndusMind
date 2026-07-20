# Download NASA CMAPSS FD001 dataset.
# Primary: kagglehub  |  Fallback: manual from NASA
import os, sys, shutil

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(DATA_DIR, 'raw')
os.makedirs(RAW_DIR, exist_ok=True)
NEEDED = ['train_FD001.txt', 'test_FD001.txt', 'RUL_FD001.txt']

def check_existing():
    return all(os.path.exists(os.path.join(RAW_DIR, f)) for f in NEEDED)

def download_kagglehub():
    try:
        import kagglehub
        path = kagglehub.dataset_download('behrad3d/nasa-cmaps')
        for root, dirs, files in os.walk(path):
            for f in files:
                if 'FD001' in f and f.endswith('.txt'):
                    src = os.path.join(root, f)
                    dst = os.path.join(RAW_DIR, f)
                    shutil.copy2(src, dst)
                    print(f'  [OK] {f}: {os.path.getsize(dst):,} bytes')
        return True
    except Exception as e:
        print(f'  kagglehub failed: {e}')
        return False

if __name__ == '__main__':
    if check_existing():
        print('Already downloaded:')
        for f in NEEDED:
            fp = os.path.join(RAW_DIR, f)
            print(f'  {f}: {os.path.getsize(fp):,} bytes')
        sys.exit(0)
    print('Downloading NASA CMAPSS FD001...')
    if not download_kagglehub():
        print('\nManual: https://www.nasa.gov/intelligent-systems-division/')
        print('         discovery-and-systems-health/pcoe/pcoe-data-set-repository/')
        print(f'         Download -> Extract -> Place in: {RAW_DIR}')
    else:
        print('\nDone!')
