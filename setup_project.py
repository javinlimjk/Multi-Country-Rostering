import os

def create_structure():
    # Define the directory structure
    structure = {
        "app": ["__init__.py", "main.py", "models.py", "optimizer.py", "compliance.py", "forecaster.py"],
        "frontend": ["dashboard.py"],
        "frontend/pages": [],
        "data/laws": [],
        "data/rosters": [],
        "tests": []
    }
    
    # Root files
    root_files = ["requirements.txt", "README.md"]

    # Create directories and files
    for folder, files in structure.items():
        try:
            os.makedirs(folder, exist_ok=True)
            print(f"✅ Created directory: {folder}")
            for file in files:
                file_path = os.path.join(folder, file)
                with open(file_path, 'w') as f:
                    pass # Create empty file
                print(f"   📄 Created file: {file_path}")
        except OSError as e:
            print(f"Error creating {folder}: {e}")

    # Create root files
    for file in root_files:
        with open(file, 'w') as f:
            pass
        print(f"📄 Created root file: {file}")

    print("\n🚀 Project scaffolding complete! You are ready to code.")

if __name__ == "__main__":
    create_structure()