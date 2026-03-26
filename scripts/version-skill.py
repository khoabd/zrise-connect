#!/usr/bin/env python3
"""
version-skill.py - Tự động tăng version và tạo changelog
Hỗ trợ tăng patch, minor, major version
"""

import os
import sys
import re
import subprocess
from datetime import datetime
from pathlib import Path

def get_current_version():
    """Đọc phiên bản hiện tại từ VERSION.md"""
    version_file = Path(__file__).parent.parent / "VERSION.md"
    if version_file.exists():
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            # Hỗ trợ định dạng: "3.3.3" hoặc "v3.3.3"
            match = re.search(r'(\d+)\.(\d+)\.(\d+)', content)
            if match:
                return tuple(int(x) for x in match.groups())
        except Exception:
            pass
    return (0, 0, 0)  # mặc định

def set_version(version_tuple):
    """Ghi phiên bản mới vào VERSION.md"""
    version_file = Path(__file__).parent.parent / "VERSION.md"
    version_str = f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"
    try:
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(version_str + "\n")
        return True
    except Exception as e:
        print(f"❌ Không thể ghi VERSION.md: {e}")
        return False

def get_git_log_since_last_tag():
    """Lấy git log từ lần tag cuối cùng đến HEAD"""
    try:
        # Lấy tag cuối cùng
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent
        )
        if result.returncode != 0:
            # Không có tag nào, lấy tất cả commit
            result = subprocess.run(
                ["git", "log", "--pretty=format:%s", "--no-merges"],
                capture_output=True, text=True, cwd=Path(__file__).parent.parent
            )
        else:
            last_tag = result.stdout.strip()
            # Lấy log từ last_tag đến HEAD (loại trừ merge commits)
            result = subprocess.run(
                ["git", "log", f"{last_tag}..HEAD", "--pretty=format:%s", "--no-merges"],
                capture_output=True, text=True, cwd=Path(__file__).parent.parent
            )
        if result.returncode == 0:
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except Exception:
        pass
    return []

def generate_changelog_entry(version_tuple, commits):
    """Tạo entrada changelog mới"""
    version_str = f"{version_tuple[0]}.{version_tuple[1]}.{version_tuple[2]}"
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    entry = f"## {version_str} ({date_str})\n\n"
    
    if commits:
        for commit in commits:
            if commit.strip():
                entry += f"- {commit.strip()}\n"
    else:
        entry += "- No specific changes recorded\n"
    
    entry += "\n"
    return entry

def update_changelog(new_entry):
    """Cập nhật file CHANGELOG.md"""
    changelog_file = Path(__file__).parent.parent / "CHANGELOG.md"
    try:
        if changelog_file.exists():
            with open(changelog_file, 'r', encoding='utf-8') as f:
                content = f.read()
        else:
            content = ""
        
        # Thêm entrada mới vào đầu
        updated_content = new_entry + content
        
        with open(changelog_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        return True
    except Exception as e:
        print(f"❌ Không thể cập nhật CHANGELOG.md: {e}")
        return False

def version_skill(bump_type):
    """Tăng version và tạo changelog"""
    skill_root = Path(__file__).parent.parent
    print(f"📦 Đang tăng version skill zrise-connect (loại: {bump_type})...")
    
    # Đọc phiên bản hiện tại
    current = get_current_version()
    print(f"📄 Phiên bản hiện tại: {current[0]}.{current[1]}.{current[2]}")
    
    # Tăng version
    if bump_type == "patch":
        new_version = (current[0], current[1], current[2] + 1)
    elif bump_type == "minor":
        new_version = (current[0], current[1] + 1, 0)
    elif bump_type == "major":
        new_version = (current[0] + 1, 0, 0)
    else:
        print(f"❌ Loại bump không hợp lệ: {bump_type}. Sử dụng: patch, minor, hoặc major")
        return 1
    
    print(f"🎯 Phiên bản mới: {new_version[0]}.{new_version[1]}.{new_version[2]}")
    
    # Ghi phiên bản mới
    if not set_version(new_version):
        return 1
    
    # Lấy git log và tạo entrada changelog
    commits = get_git_log_since_last_tag()
    changelog_entry = generate_changelog_entry(new_version, commits)
    
    # Cập nhật CHANGELOG.md
    if not update_changelog(changelog_entry):
        return 1
    
    print("✅ Đã cập nhật VERSION.md và CHANGELOG.md")
    print(f"📓 Entrada changelog mới đã được thêm vào CHANGELOG.md")
    
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 version-skill.py [patch|minor|major]")
        print("Example: python3 version-skill.py patch")
        sys.exit(1)
    
    bump_type = sys.argv[1].lower()
    if bump_type not in ["patch", "minor", "major"]:
        print("❌ Loại bump không hợp lệ. Sử dụng: patch, minor, hoặc major")
        sys.exit(1)
    
    sys.exit(version_skill(bump_type))
