import subprocess
with open('requirements.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            print(f"Installing {line}...")
            subprocess.run(['pip', 'install', line])
