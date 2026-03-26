#!/usr/bin/env python3
"""
lint-skill.py - Tự động lint và định dạng code
Kiểm tra chất lượng code Python và YAML
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, cwd=None):
    """Chạy lệnh và trả về (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def lint_skill():
    """Lint và định dạng code skill zrise-connect"""
    skill_root = Path(__file__).parent.parent
    print("🧹 Đang lint và định dạng code skill zrise-connect...")
    print(f"📁 Thư mục skill: {skill_root}")

    issues = []
    fixed = []

    # 1. Lint Python files với pylint hoặc flake8
    scripts_dir = skill_root / "scripts"
    if scripts_dir.exists():
        # Thử pylint trước
        returncode, stdout, stderr = run_command("pylint --version")
        if returncode == 0:
            for py_file in scripts_dir.glob("*.py"):
                returncode, stdout, stderr = run_command(f"pylint {py_file}")
                if returncode != 0:
                    issues.append(f"⚠️ pylint cảnh báo trong {py_file.name}:\n{stdout}")
                else:
                    # Tự động định dạng bằng autopep8 nếu có sẵn
                    returncode2, stdout2, stderr2 = run_command("autopep8 --version")
                    if returncode2 == 0:
                        returncode3, stdout3, stderr3 = run_command(f"autopep8 --in-place --aggressive {py_file}")
                        if returncode3 == 0 and stdout3.strip() == "":
                            fixed.append(f"🎨 Đã định dạng code bằng autopep8: {py_file.name}")
                        else:
                            # Nếu không thể tự động định dạng, chỉ báo lỗi
                            pass
        else:
            # Thử flake8 nếu pylint không có sẵn
            returncode, stdout, stderr = run_command("flake8 --version")
            if returncode == 0:
                for py_file in scripts_dir.glob("*.py"):
                    returncode, stdout, stderr = run_command(f"flake8 {py_file}")
                    if returncode != 0:
                        issues.append(f"⚠️ flake8 cảnh báo trong {py_file.name}:\n{stdout}")
                    else:
                        # Tự động định dạng bằng autopep8
                        returncode2, stdout2, stderr2 = run_command("autopep8 --version")
                        if returncode2 == 0:
                            returncode3, stdout3, stderr3 = run_command(f"autopep8 --in-place --aggressive {py_file}")
                            if returncode3 == 0 and stdout3.strip() == "":
                                fixed.append(f"🎨 Đã định dạng code bằng autopep8: {py_file.name}")

    # 2. Lint YAML files với yamllint (nếu có sẵn)
    configs_dir = skill_root / "configs"
    if configs_dir.exists():
        returncode, stdout, stderr = run_command("yamllint --version")
        if returncode == 0:
            for yaml_file in configs_dir.glob("*.yaml") + configs_dir.glob("*.yml"):
                returncode, stdout, stderr = run_command(f"yamllint {yaml_file}")
                if returncode != 0:
                    issues.append(f"⚠️ yamllint cảnh báo trong {yaml_file.name}:\n{stdout}")

    # 3. Lint Markdown files với markdownlint (nếu có sẵn)
    docs_dir = skill_root / "docs"
    if docs_dir.exists():
        returncode, stdout, stderr = run_command("markdownlint --version")
        if returncode == 0:
            for md_file in docs_dir.glob("*.md"):
                returncode, stdout, stderr = run_command(f"markdownlint {md_file}")
                if returncode != 0:
                    issues.append(f"⚠️ markdownlint cảnh báo trong {md_file.name}:\n{stdout}")

    # In kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ LINT VÀ ĐỊNH DẠNG CODE")
    print("="*60)

    if fixed:
        print("✅ Đã tự động định dạng các file sau:")
        for f in fixed:
            print(f"  {f}")

    if issues:
        print("\n⚠️ CẦN CHIẾU THỬ LẠI (cần xử lý tay):")
        for issue in issues:
            print(f"  {issue[:200]}{'...' if len(issue) > 200 else ''}")
    else:
        print("\n✅ Không có vấn đề lint nào được phát hiện")

    # Trả về mã thoát
    if issues:
        print("\n📋 KẾT LUẬN: Cần xử lý tay một số vấn đề lint")
        return 1
    else:
        print("\n📋 KẾT LUẬN: Code đã sạch và được định dạng đúng")
        return 0

if __name__ == "__main__":
    sys.exit(lint_skill())
