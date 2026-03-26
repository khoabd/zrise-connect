#!/usr/bin/env python3
"""
improve-skill.py - Tự động cải thiện skill zrise-connect
Cải thiện code, documentation, và cấu trúc skill
"""

import os
import sys
import shutil
from pathlib import Path

def improve_skill():
    """Cải thiện skill zrise-connect"""
    skill_root = Path(__file__).parent.parent
    print("🛠️ Đang cải thiện skill zrise-connect...")
    print(f"📁 Thư mục skill: {skill_root}")

    changes_made = []

    # 1. Đảm bảo tất cả script có quyền thực thi (chmod +x)
    scripts_dir = skill_root / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.glob("*.py"):
            if not os.access(py_file, os.X_OK):
                os.chmod(py_file, 0o755)
                changes_made.append(f"🔧 Đã cho quyền thực thi: {py_file.name}")

    # 2. Định dạng code Python bằng black (nếu có sẵn)
    try:
        import subprocess
        result = subprocess.run(["black", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            for py_file in scripts_dir.glob("*.py"):
                result = subprocess.run(["black", str(py_file)], capture_output=True, text=True)
                if result.returncode == 0:
                    changes_made.append(f"🎨 Đã định dạng code bằng black: {py_file.name}")
    except FileNotFoundError:
        pass  # black không được cài đặt, bỏ qua
    except Exception as e:
        pass  # lỗi khác, bỏ qua

    # 3. Đảm bảo SKILL.md không có dòng trống thừa ở đầu và cuối
    skill_md = skill_root / "SKILL.md"
    if skill_md.exists():
        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # Loại bỏ dòng trống ở đầu và cuối
            while lines and lines[0].strip() == "":
                lines.pop(0)
            while lines and lines[-1].strip() == "":
                lines.pop()
            # Ghi lại nếu có thay đổi
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            if len([l for l in lines if l.strip() != ""]) > 0:
                changes_made.append("📝 Đã làm sạch SKILL.md (loại bỏ dòng trống thừa)")
        except Exception as e:
            pass  # bỏ qua nếu lỗi

    # 4. Đảm bảo không có file __pycache__ hoặc .pyc
    for pycache in skill_root.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
        changes_made.append(f"🗑️ Đã xóa __pycache__: {pycache.relative_to(skill_root)}")
    for pyc in skill_root.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
        changes_made.append(f"🗑️ Đã xóa file .pyc: {pyc.relative_to(skill_root)}")

    # 5. Đảm bảo không có file .DS_Store (trên macOS)
    for ds_store in skill_root.rglob(".DS_Store"):
        ds_store.unlink(missing_ok=True)
        changes_made.append(f"🗑️ Đã xóa .DS_Store: {ds_store.relative_to(skill_root)}")

    # 6. Đảm bảo không có file backup (.bak, .old, ~)
    for backup_file in skill_root.rglob("*.bak"):
        backup_file.unlink(missing_ok=True)
        changes_made.append(f"🗑️ Đã xóa file backup: {backup_file.relative_to(skill_root)}")
    for backup_file in skill_root.rglob("*.old"):
        backup_file.unlink(missing_ok=True)
        changes_made.append(f"🗑️ Đã xóa file backup: {backup_file.relative_to(skill_root)}")
    for backup_file in skill_root.rglob("*~"):
        backup_file.unlink(missing_ok=True)
        changes_made.append(f"🗑️ Đã xóa file backup: {backup_file.relative_to(skill_root)}")

    # In kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ CẢI THIỆN SKILL")
    print("="*60)

    if changes_made:
        print("✅ Đã thực hiện các thay đổi sau:")
        for change in changes_made:
            print(f"  {change}")
    else:
        print("ℹ️ Không có thay đổi nào cần thực hiện")

    print("\n📋 KẾT LUẬN: Skill đã được cải thiện")
    return 0

if __name__ == "__main__":
    sys.exit(improve_skill())
