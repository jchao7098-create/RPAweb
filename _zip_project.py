import zipfile
import os

root = r'D:\RPAweb'
output = r'D:\RPAweb\RPAweb_backup_20260723_161345.zip'
exclude_dirs = {'node_modules', '__pycache__', '.git', 'dist', '.workbuddy'}
exclude_ext = {'.pyc', '.log'}

count = 0
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out excluded directories from traversal
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in exclude_ext:
                continue
            filepath = os.path.join(dirpath, fname)
            arcname = os.path.relpath(filepath, root)
            zf.write(filepath, arcname)
            count += 1

size_mb = os.path.getsize(output) / 1024 / 1024
print(f'Done: {count} files, {size_mb:.1f} MB')
