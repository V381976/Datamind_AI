from pathlib import Path
for path in sorted(Path('.next/static/css').rglob('*')):
    if path.is_file():
        print(path)
