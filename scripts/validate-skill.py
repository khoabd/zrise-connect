#!/usr/bin/env python3
"""
validate-skill.py - Tự động xác thực skill zrise-connect
Kiểm tra xem skill có tuân thủ chuẩn OpenClaw không
"""

import os
import sys
import re
from pathlib import Path

def validate_skill():
    """Xác thực skill zrise-connect"""
    skill_root = Path(__file__).parent.parent
    errors = []
    warnings = []

    print("🔍 Đang xác thực skill zrise-connect...")
    print(f"📁 Thư mục skill: {skill_root}")

    # 1. Kiểm tra SKILL.md tồn tại và có đủ thông tin
    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        errors.append("❌ Thiếu file SKILL.md")
    else:
        try:
            with open(skill_md, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content.strip()) < 50:
                warnings.append("⚠️ SKILL.md có vẻ quá ngắn (< 50 ký tự)")
            if "Mô tả" not in content and "Description" not in content:
                warnings.append("⚠️ SKILL.md có thể thiếu phần mô tả")
        except Exception as e:
            errors.append(f"❌ Không thể đọc SKILL.md: {e}")

    # 2. Kiểm tra VERSION.md tồn tại
    version_md = skill_root / "VERSION.md"
    if not version_md.exists():
        errors.append("❌ Thiếu file VERSION.md")
    else:
        try:
            with open(version_md, 'r', encoding='utf-8') as f:
                version = f.read().strip()
                if not re.match(r'^\d+\.\d+\.\d+$', version):
                    warnings.append(f"⚠️ VERSION.md không đúng format semver: {version}")
        except Exception as e:
            errors.append(f"❌ Không thể đọc VERSION.md: {e}")

    # 3. Kiểm tra CHANGELOG.md tồn tại
    changelog_md = skill_root / "CHANGELOG.md"
    if not changelog_md.exists():
        warnings.append("⚠️ Thiếu file CHANGELOG.md (khuyên dùng)")

    # 4. Kiểm tra scripts tồn tại và có chmod +x
    scripts_dir = skill_root / "scripts"
    if not scripts_dir.exists():
        errors.append("❌ Thiếu thư mục scripts/")
    else:
        required_scripts = [
            "auto_plan.py",
            "accept_default_plan.py", 
            "config_agent.py",
            "regenerate_plan.py",
            "execute_task.py",
            "claim_and_process.py",
            "writeback_to_zrise.py",
            "poll_employee_work.py"
        ]
        for script_name in required_scripts:
            script_path = scripts_dir / script_name
            if not script_path.exists():
                errors.append(f"❌ Thiếu script: {script_name}")
            else:
                # Kiểm tra quyền thực thi
                if not os.access(script_path, os.X_OK):
                    warnings.append(f"⚠️ Script {script_name} không có quyền thực thi (chmod +x)")

    # 5. Kiểm tra workflows tồn tại
    workflows_dir = skill_root / "workflows"
    if not workflows_dir.exists():
        errors.append("❌ Thiếu thư mục workflows/")
    else:
        required_workflows = ["zrise-execute.lobster", "general.lobster"]
        for wf_name in required_workflows:
            if not (workflows_dir / wf_name).exists():
                warnings.append(f"⚠️ Thiếu workflow: {wf_name}")

    # 6. Kiểm tra không có sensitive data trong code
    sensitive_patterns = [
        r'(?i)password\s*=\s*["\'][^"\']*["\']',
        r'(?i)token\s*=\s*["\'][^"\']*["\']',
        r'(?i)api_key\s*=\s*["\'][^"\']*["\']',
        r'(?i)secret\s*=\s*["\'][^"\']*["\']',
        r'(?i)credentials\s*=\s*["\'][^"\']*["\']'
    ]
    for py_file in scripts_dir.glob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            for pattern in sensitive_patterns:
                if re.search(pattern, content):
                    # Bỏ qua nếu là trong comment hoặc docstring
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line) and not line.strip().startswith('#'):
                            errors.append(f"❌ Phát hiện sensitive data có thể vô ý trong {py_file.name}:{i+1}")
        except Exception as e:
            warnings.append(f"⚠️ Không thể đọc {py_file.name} để kiểm tra sensitive data: {e}")

    # In kết quả
    print("\n" + "="*60)
    print("KẾT QUẢ XÁC THỰC SKILL")
    print("="*60)

    if errors:
        print("❌ LỖI:")
        for error in errors:
            print(f"  {error}")
    else:
        print("✅ Không tìm thấy lỗi nghiêm trọng")

    if warnings:
        print("\n⚠️ CẢNH BÁO:")
        for warning in warnings:
            print(f"  {warning}")
    else:
        print("\n✅ Không có cảnh báo")

    # Trả về mã thoát
    if errors:
        print("\n📋 KẾT LUẬN: Skill KHÔNG ĐỦ CHUẨN - Cần sửa lỗi")
        return 1
    else:
        print("\n📋 KẾT LUẬN: Skill ĐỦ CHUẨN OPENCLAW")
        return 0

if __name__ == "__main__":
    sys.exit(validate_skill())
