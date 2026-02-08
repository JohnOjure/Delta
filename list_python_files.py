import os

def list_python_files(path):
    python_files = []
    for item in os.listdir(path):
        full_path = os.path.join(path, item)
        if os.path.isfile(full_path) and item.endswith('.py'):
            python_files.append(item)
    return python_files


if __name__ == "__main__":
    current_directory = os.getcwd()
    python_files = list_python_files(current_directory)
    for file in python_files:
        print(file)
