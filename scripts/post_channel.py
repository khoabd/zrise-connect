#!/usr/bin/env python3
"""
post_channel.py - Send messages via OpenClaw's native channel routing.

OpenClaw handles Telegram/Discord/Slack automatically based on config.
Uses the 'openclaw message send' CLI command for sending.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Union

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from zrise_utils import load_json, get_openclaw_config_path


def get_channel_config() -> dict:
    """Load channel configuration from OpenClaw config."""
    config_path = get_openclaw_config_path()
    cfg = load_json(config_path)
    
    # Get Telegram settings from zrise-connect skill config
    skill_cfg = cfg.get('skills', {}).get('entries', {}).get('zrise-connect', {})
    env = skill_cfg.get('env', {})
    
    return {
        'bot_token': env.get('TELEGRAM_BOT_TOKEN'),
        'default_chat_id': env.get('TELEGRAM_CHAT_ID'),
        'default_target': env.get('TELEGRAM_CHAT_ID'),  # Alias for clarity
        'parse_mode': env.get('TELEGRAM_PARSE_MODE', 'Markdown'),
    }


def get_default_target() -> Optional[str]:
    """Get default target (chat ID) from config."""
    config = get_channel_config()
    return config.get('default_target')


def send_channel_message(
    text: str,
    buttons: List = None,
    channel: str = None,
    target: str = None,
    parse_mode: str = "Markdown",
    silent: bool = False
) -> dict:
    """
    Send message via OpenClaw's message tool.
    
    OpenClaw auto-routes to correct channel (Telegram/Discord/Slack) based on config.
    
    Args:
        text: Message text (supports Markdown)
        buttons: List of button rows, each row is a list of buttons.
                 Each button: {"text": "Label", "callback_data": "data"} or
                              {"text": "Label", "url": "https://..."}
                 Style options: "primary", "success", "danger"
        channel: "telegram", "discord", "slack", or None (auto-detect from config)
        target: Specific target (user/group ID). Uses default if not provided.
        parse_mode: "Markdown" or "HTML" (default: Markdown)
        silent: Send without notification
    
    Returns:
        {"success": True, "message_id": <id>, "raw": <response>} or 
        {"success": False, "error": <msg>}
    
    Example buttons:
        buttons = [
            [{"text": "✅ APPROVE", "callback_data": "approve_4", "style": "success"}, 
             {"text": "💬 FEEDBACK", "callback_data": "feedback_4", "style": "primary"}]
        ]
    """
    try:
        # Build command
        cmd = ["openclaw", "message", "send"]
        
        # Add channel if specified
        if channel:
            cmd.extend(["--channel", channel])
        
        # Add target if specified
        if target:
            cmd.extend(["--target", target])
        
        # Add silent flag
        if silent:
            cmd.append("--silent")
        
        # Add buttons if provided
        if buttons:
            # Normalize buttons format
            normalized_buttons = _normalize_buttons(buttons)
            cmd.extend(["--buttons", json.dumps(normalized_buttons)])
        
        # Add message via stdin to avoid shell escaping issues
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate(input=text, timeout=30)
        
        if process.returncode == 0:
            try:
                result = json.loads(stdout) if stdout else {"success": True}
                return {
                    "success": True,
                    "raw": result,
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "raw": stdout.strip(),
                }
        else:
            return {
                "success": False,
                "error": stderr.strip() or f"Exit code {process.returncode}",
                "stderr": stderr,
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Message send timed out",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "OpenClaw CLI not found. Is openclaw installed?",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def _normalize_buttons(buttons: List) -> List[dict]:
    """
    Normalize buttons format for OpenClaw message tool.
    
    OpenClaw expects: [{"text": "...", "callback_data": "...", "style": "primary"}, ...]
    
    Args:
        buttons: List of button rows (nested lists) or flat list
    
    Returns:
        Flat list of normalized button dicts
    """
    normalized = []
    
    for row in buttons:
        if isinstance(row, list):
            for btn in row:
                normalized.append(_normalize_single_button(btn))
        else:
            normalized.append(_normalize_single_button(row))
    
    return normalized


def _normalize_single_button(btn: dict) -> dict:
    """Normalize a single button dict."""
    normalized = {
        "text": btn.get("text", ""),
    }
    
    if "callback_data" in btn:
        normalized["callback_data"] = btn["callback_data"]
    if "url" in btn:
        normalized["url"] = btn["url"]
    if "style" in btn:
        normalized["style"] = btn["style"]
    
    return normalized


def send_with_approve_feedback(
    target: str,
    text: str,
    job_id: int,
    parse_mode: str = "Markdown",
    channel: str = None
) -> dict:
    """
    Send message with standard APPROVE/FEEDBACK buttons.
    
    Args:
        target: Chat ID (user or channel)
        text: Message text
        job_id: Job ID for callback data
        parse_mode: Parse mode (default: Markdown)
        channel: Channel to use (default: auto-detect)
    
    Returns:
        Result dict with success status
    """
    buttons = [
        [
            {"text": "✅ APPROVE", "callback_data": f"approve_{job_id}", "style": "success"},
            {"text": "💬 FEEDBACK", "callback_data": f"feedback_{job_id}", "style": "primary"},
        ]
    ]
    
    return send_channel_message(
        text=text,
        buttons=buttons,
        channel=channel,
        target=target,
        parse_mode=parse_mode
    )


def format_text(text: str, max_length: int = 4096) -> str:
    """
    Format text for messaging, handling Markdown special characters.
    
    Args:
        text: Raw text
        max_length: Max message length (Telegram limit is 4096)
    
    Returns:
        Formatted text ready for sending
    """
    # Escape special Markdown characters for Telegram
    # Note: Discord uses different escaping, but OpenClaw handles per-channel
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length - 50] + "\n\n... _(truncated)_"
    
    return text


# Backwards compatibility aliases
def send_telegram_message(chat_id: str, text: str, buttons: list = None, parse_mode: str = "Markdown", silent: bool = False) -> dict:
    """Backwards compatibility wrapper for send_telegram_message."""
    return send_channel_message(
        text=text,
        buttons=buttons,
        channel="telegram",
        target=chat_id,
        parse_mode=parse_mode,
        silent=silent
    )


def get_default_chat_id() -> Optional[str]:
    """Backwards compatibility - returns default target."""
    return get_default_target()


if __name__ == '__main__':
    # Test script
    print("=== post_channel.py Test ===")
    
    config = get_channel_config()
    print(f"Bot Token: {'*' * 20}{config['bot_token'][-10:] if config['bot_token'] else 'NOT SET'}")
    print(f"Default Target: {config['default_target'] or 'NOT SET'}")
    
    # Test message
    test_target = config.get('default_target') or "TEST_TARGET"
    result = send_channel_message(
        text="🧪 *Test Message*\n\nThis is a test from post_channel.py using OpenClaw routing",
        buttons=[
            [
                {"text": "✅ APPROVE", "callback_data": "approve_test", "style": "success"},
                {"text": "💬 FEEDBACK", "callback_data": "feedback_test", "style": "primary"},
            ]
        ],
        target=test_target,
        channel="telegram"  # Explicit for testing
    )
    print(f"\nTest Result: {json.dumps(result, indent=2)}")
