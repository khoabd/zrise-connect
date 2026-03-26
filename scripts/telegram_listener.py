#!/usr/bin/env python3
"""
telegram_listener.py - Listen for Telegram callbacks/responses and route to handlers.

This script polls Telegram for button clicks (callbacks) and text responses,
then routes them to the appropriate handlers (handle_review_response.py).

Usage:
    python3 telegram_listener.py --once    # For cron (single poll)
    python3 telegram_listener.py            # Daemon mode (continuous polling)
    python3 telegram_listener.py --poll-interval 30  # Custom interval

Note: For production, consider using Telegram Webhooks instead of polling.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from zrise_utils import load_json, get_openclaw_config_path, get_state_path
from db import init_db, add_task_log


# === CONFIGURATION ===

def get_telegram_config() -> dict:
    """Load Telegram configuration from OpenClaw config."""
    config_path = get_openclaw_config_path()
    cfg = load_json(config_path)
    
    skill_cfg = cfg.get('skills', {}).get('entries', {}).get('zrise-connect', {})
    env = skill_cfg.get('env', {})
    
    return {
        'bot_token': env.get('TELEGRAM_BOT_TOKEN'),
        'default_chat_id': env.get('TELEGRAM_CHAT_ID'),
        'api_url': f"https://api.telegram.org/bot{env.get('TELEGRAM_BOT_TOKEN', '')}",
    }


def get_state_file(name: str) -> Path:
    """Get path for state file."""
    return get_state_path(f"telegram_{name}.json")


def load_callback_offset() -> Optional[int]:
    """Load last processed callback offset."""
    state_file = get_state_file("callback_offset")
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding='utf-8'))
            return data.get('offset')
        except:
            return None
    return None


def save_callback_offset(offset: int):
    """Save last processed callback offset."""
    state_file = get_state_file("callback_offset")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({'offset': offset, 'updated': datetime.now().isoformat()}), encoding='utf-8')


# === CALLBACK PARSING ===

def parse_callback(callback_data: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse callback data like 'approve_4' or 'feedback_5'.
    
    Args:
        callback_data: Raw callback_data string from Telegram
    
    Returns:
        Tuple of (action, job_id) where action is 'approve' or 'feedback'
        Returns (None, None) if parsing fails
    
    Examples:
        "approve_4" -> ("approve", 4)
        "feedback_5" -> ("feedback", 5)
        "unknown_1" -> (None, None)
    """
    if not callback_data:
        return None, None
    
    # Match patterns: approve_<number>, feedback_<number>
    approve_match = re.match(r'^approve[_\s]?(\d+)$', callback_data, re.IGNORECASE)
    if approve_match:
        return 'approve', int(approve_match.group(1))
    
    feedback_match = re.match(r'^feedback[_\s]?(\d+)$', callback_data, re.IGNORECASE)
    if feedback_match:
        return 'feedback', int(feedback_match.group(1))
    
    # Also support simple patterns without number
    if callback_data.lower() == 'approve':
        return 'approve', None
    if callback_data.lower() == 'feedback':
        return 'feedback', None
    
    return None, None


def parse_text_response(text: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parse text response like "APPROVE" or "FEEDBACK: some text" or "FEEDBACK 4: text".
    
    Args:
        text: Response text from user
    
    Returns:
        Tuple of (action, job_id, extra_text)
    
    Examples:
        "APPROVE" -> ("approve", None, None)
        "FEEDBACK: add more details" -> ("feedback", None, "add more details")
        "APPROVE 4" -> ("approve", 4, None)
        "FEEDBACK 4: use async" -> ("feedback", 4, "use async")
    """
    if not text:
        return None, None, None
    
    text = text.strip()
    
    # APPROVE patterns
    approve_match = re.match(r'^APPROVE\s*#?(\d+)?\s*$', text, re.IGNORECASE)
    if approve_match:
        job_id = int(approve_match.group(1)) if approve_match.group(1) else None
        return 'approve', job_id, None
    
    # FEEDBACK patterns
    feedback_match = re.match(r'^FEEDBACK\s*#?(\d+)?[:\s]+(.+)$', text, re.IGNORECASE)
    if feedback_match:
        job_id = int(feedback_match.group(1)) if feedback_match.group(1) else None
        feedback_text = feedback_match.group(2).strip()
        return 'feedback', job_id, feedback_text
    
    return None, None, None


# === HANDLER ROUTING ===

def handle_callback(action: str, job_id: int, message_id: str = None, chat_id: str = None) -> dict:
    """
    Handle button click callbacks.
    
    Args:
        action: 'approve' or 'feedback'
        job_id: Job ID from callback data
        message_id: Original message ID (for acknowledgment)
        chat_id: Chat ID (for sending response)
    
    Returns:
        Result dict from handler
    """
    script_path = Path(__file__).parent / "handle_review_response.py"
    
    if action == 'approve':
        cmd = [
            sys.executable, str(script_path),
            '--job-id', str(job_id),
            '--approve'
        ]
        description = f"APPROVE Job #{job_id}"
        
    elif action == 'feedback':
        # For feedback, we need to prompt for text (handled separately)
        cmd = None
        description = f"FEEDBACK Job #{job_id} (awaiting text)"
        
    else:
        return {
            'success': False,
            'error': f'Unknown action: {action}'
        }
    
    if cmd:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(__file__).parent)
            )
            
            return {
                'success': result.returncode == 0,
                'action': action,
                'job_id': job_id,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'description': description,
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Handler timed out',
                'action': action,
                'job_id': job_id,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'action': action,
                'job_id': job_id,
            }
    
    return {
        'success': True,
        'action': action,
        'job_id': job_id,
        'description': description,
        'awaiting_feedback': True,
    }


def handle_feedback_text(job_id: int, feedback_text: str) -> dict:
    """
    Handle FEEDBACK text response.
    
    Args:
        job_id: Job ID
        feedback_text: User's feedback text
    
    Returns:
        Result dict from handler
    """
    script_path = Path(__file__).parent / "handle_review_response.py"
    
    cmd = [
        sys.executable, str(script_path),
        '--job-id', str(job_id),
        '--feedback', feedback_text
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent)
        )
        
        return {
            'success': result.returncode == 0,
            'action': 'feedback',
            'job_id': job_id,
            'feedback': feedback_text,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Handler timed out',
            'action': 'feedback',
            'job_id': job_id,
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'action': 'feedback',
            'job_id': job_id,
        }


def acknowledge_callback(bot_token: str, callback_id: str, text: str = None):
    """
    Acknowledge a callback query (required by Telegram API).
    
    Args:
        bot_token: Telegram bot token
        callback_id: Callback query ID
        text: Optional text to show in snackbar
    """
    import urllib.request
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    data = {
        'callback_query_id': callback_id,
    }
    if text:
        data['text'] = text
        data['show_alert'] = 'true'
    
    try:
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode(),
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"⚠️ Failed to acknowledge callback: {e}")


# === TELEGRAM API POLLING ===

def poll_telegram_updates(bot_token: str, offset: int = None, timeout: int = 30) -> dict:
    """
    Poll Telegram for updates using getUpdates API.
    
    Args:
        bot_token: Telegram bot token
        offset: Update offset (for avoiding duplicates)
        timeout: Long polling timeout in seconds
    
    Returns:
        dict with 'callbacks', 'messages', 'offset'
    """
    import urllib.request
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params = {'timeout': timeout}
    if offset:
        params['offset'] = offset
    
    url_with_params = url + '?' + urllib.parse.urlencode(params)
    
    try:
        with urllib.request.urlopen(url_with_params, timeout=timeout + 5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if not data.get('ok'):
                return {
                    'success': False,
                    'error': data.get('description', 'Unknown error'),
                    'callbacks': [],
                    'messages': [],
                }
            
            updates = data.get('result', [])
            
            callbacks = []
            text_messages = []
            new_offset = offset
            
            for update in updates:
                update_id = update.get('update_id', 0)
                if new_offset is None or update_id >= new_offset:
                    new_offset = update_id + 1
                
                # Check for callback_query
                callback_query = update.get('callback_query')
                if callback_query:
                    callback_data = callback_query.get('data')
                    message_id = str(callback_query.get('message', {}).get('message_id', ''))
                    chat_id = str(callback_query.get('message', {}).get('chat', {}).get('id', ''))
                    
                    callbacks.append({
                        'callback_id': callback_query.get('id'),
                        'data': callback_data,
                        'message_id': message_id,
                        'chat_id': chat_id,
                        'from_id': str(callback_query.get('from', {}).get('id', '')),
                        'from_name': callback_query.get('from', {}).get('first_name', ''),
                    })
                
                # Check for regular message with text
                message = update.get('message')
                if message and message.get('text'):
                    text_messages.append({
                        'message_id': str(message.get('message_id', '')),
                        'chat_id': str(message.get('chat', {}).get('id', '')),
                        'text': message.get('text', ''),
                        'from_id': str(message.get('from', {}).get('id', '')),
                        'from_name': message.get('from', {}).get('first_name', ''),
                        'date': message.get('date'),
                    })
            
            return {
                'success': True,
                'callbacks': callbacks,
                'messages': text_messages,
                'offset': new_offset,
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'callbacks': [],
            'messages': [],
        }


def process_updates(config: dict, once: bool = False, poll_interval: int = 5) -> int:
    """
    Process Telegram updates in a loop.
    
    Args:
        config: Telegram config dict
        once: If True, process once and exit (for cron)
        poll_interval: Seconds between polls (daemon mode)
    
    Returns:
        Number of callbacks/messages processed
    """
    bot_token = config.get('bot_token')
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not configured")
        return 0
    
    offset = load_callback_offset()
    if offset is None:
        offset = 0
    
    processed = 0
    
    while True:
        result = poll_telegram_updates(bot_token, offset, timeout=min(poll_interval, 30))
        
        if not result.get('success'):
            print(f"⚠️ Poll error: {result.get('error')}")
        else:
            # Save offset
            new_offset = result.get('offset')
            if new_offset and new_offset != offset:
                save_callback_offset(new_offset)
                offset = new_offset
            
            # Process callbacks
            for callback in result.get('callbacks', []):
                callback_id = callback['callback_id']
                callback_data = callback['data']
                message_id = callback['message_id']
                chat_id = callback['chat_id']
                
                action, job_id = parse_callback(callback_data)
                
                if action and job_id:
                    print(f"📩 Callback: {action} for Job #{job_id}")
                    
                    # Handle the callback
                    handler_result = handle_callback(action, job_id, message_id, chat_id)
                    
                    if handler_result.get('success'):
                        acknowledge_callback(bot_token, callback_id, f"✅ {action.title()} processed")
                        print(f"   ✅ {handler_result.get('description', action)}")
                    else:
                        acknowledge_callback(bot_token, callback_id, f"❌ Error: {handler_result.get('error', 'Unknown')}")
                        print(f"   ❌ Failed: {handler_result.get('error')}")
                    
                    processed += 1
                else:
                    print(f"⚠️ Unknown callback data: {callback_data}")
                    acknowledge_callback(bot_token, callback_id, f"❓ Unknown action: {callback_data}")
            
            # Process text messages
            for msg in result.get('messages', []):
                text = msg['text']
                chat_id = msg['chat_id']
                
                action, job_id, extra = parse_text_response(text)
                
                if action == 'approve' and job_id:
                    print(f"📩 Text APPROVE for Job #{job_id}")
                    handler_result = handle_callback('approve', job_id)
                    
                    if handler_result.get('success'):
                        print(f"   ✅ Approved Job #{job_id}")
                    else:
                        print(f"   ❌ Failed: {handler_result.get('error')}")
                    processed += 1
                    
                elif action == 'feedback' and job_id:
                    print(f"📩 Text FEEDBACK for Job #{job_id}")
                    
                    if extra:
                        # Feedback with text
                        handler_result = handle_feedback_text(job_id, extra)
                        if handler_result.get('success'):
                            print(f"   ✅ Feedback recorded for Job #{job_id}")
                        else:
                            print(f"   ❌ Failed: {handler_result.get('error')}")
                    else:
                        # Just "FEEDBACK" - prompt for more
                        print(f"   ℹ️ Feedback recorded, awaiting text...")
                        # In a full implementation, would send a prompt message
                    processed += 1
        
        if once:
            break
        
        time.sleep(poll_interval)
    
    return processed


# === MAIN ===

def main():
    parser = argparse.ArgumentParser(
        description='Listen for Telegram callbacks and route to handlers',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python3 telegram_listener.py --once              # Single poll for cron
    python3 telegram_listener.py                     # Daemon mode
    python3 telegram_listener.py --poll-interval 10 # 10 second interval
        """
    )
    parser.add_argument('--once', action='store_true', help='Poll once and exit (for cron)')
    parser.add_argument('--poll-interval', type=int, default=5, help='Poll interval in seconds (daemon mode)')
    
    args = parser.parse_args()
    
    print("=== Telegram Listener ===")
    print(f"Mode: {'Single poll' if args.once else 'Daemon'}")
    print(f"Poll interval: {args.poll_interval}s")
    
    config = get_telegram_config()
    print(f"Bot token: {'*' * 20}{config.get('bot_token', '')[-10:] if config.get('bot_token') else 'NOT SET'}")
    print(f"Default chat: {config.get('default_chat_id') or 'NOT SET'}")
    print()
    
    if not config.get('bot_token'):
        print("❌ TELEGRAM_BOT_TOKEN not configured in openclaw.json")
        sys.exit(1)
    
    init_db()
    
    try:
        processed = process_updates(config, once=args.once, poll_interval=args.poll_interval)
        print(f"\n📊 Processed {processed} updates")
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
