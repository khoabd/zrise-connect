#!/usr/bin/env python3
"""
post_to_telegram.py - DEPRECATED - Redirects to post_channel.py

This module is kept for backwards compatibility.
Use post_channel.py instead which uses OpenClaw's native channel routing.
"""

# Re-export from post_channel for backwards compatibility
from post_channel import (
    send_channel_message as send_telegram_message,
    get_default_target as get_default_chat_id,
    format_text as format_telegram_text,
    send_with_approve_feedback as send_telegram_with_approve_feedback,
    send_channel_message,
    get_default_target,
    format_text,
)

__all__ = [
    'send_telegram_message',
    'get_default_chat_id', 
    'format_telegram_text',
    'send_telegram_with_approve_feedback',
    'send_channel_message',
    'get_default_target',
    'format_text',
]


if __name__ == '__main__':
    print("=== post_to_telegram.py is DEPRECATED ===")
    print("Please use post_channel.py instead which uses OpenClaw's native channel routing.")
    print()
    print("Migration:")
    print("  Old: from post_to_telegram import send_telegram_message")
    print("  New: from post_channel import send_channel_message")
