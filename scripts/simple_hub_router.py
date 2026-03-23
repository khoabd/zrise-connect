#!/usr/bin/env python3
"""
Simple Hub Router for Zrise Connect
Uses agent_registry.yaml to map tasks to agents
"""
import yaml
import json
import sys
import os
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.resolve()
REGISTRY_PATH = SCRIPTS_DIR.parent.parent.parent / 'agent_registry.yaml'


class SimpleHubRouter:
    def __init__(self):
        self.registry = self._load_registry()
    
    def _load_registry(self):
        """Load agent registry from YAML file"""
        try:
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('registry', {})
        except FileNotFoundError:
            print(f"⚠️ Registry file not found: {REGISTRY_PATH}", file=sys.stderr)
            return self._default_registry()
        except Exception as e:
            print(f"⚠️ Failed to load registry: {e}", file=sys.stderr)
            return self._default_registry()
    
    def _default_registry(self):
        """Return minimal default registry"""
        return {
            'fallback': {'general': 'general-agent'},
            'user_overrides': {}
        }
    
    def route_task(self, task):
        """
        Route task to appropriate agent based on registry
        
        Args:
            task: dict containing task data from Zrise
                  Expected keys: department, type, user_id (optional)
                  
        Returns:
            agent_name: string (e.g., 'sales-agent')
        """
        dept = str(task.get('department', '')).lower().strip()
        task_type = str(task.get('type', '')).lower().strip()
        user_id = str(task.get('user_id', '')).strip()
        
        # 1. Check user override (highest priority)
        if user_id and user_id in self.registry.get('user_overrides', {}):
            override = self.registry['user_overrides'][user_id]
            if task_type in override:
                agent = override[task_type]
                # print(f"🔧 User override: {user_id} → {task_type} → {agent}", file=sys.stderr)
                return agent
        
        # 2. Check department mapping
        if dept in self.registry and task_type in self.registry[dept]:
            agent = self.registry[dept][task_type]
            # print(f"📍 Registry match: {dept}/{task_type} → {agent}", file=sys.stderr)
            return agent
        
        # 3. Fallback logic
        # Try general fallback first
        if 'general' in self.registry.get('fallback', {}):
            return self.registry['fallback']['general']
        
        # Try unknown-type fallback
        if task_type and 'unknown-type' in self.registry.get('fallback', {}):
            return self.registry['fallback']['unknown-type']
            
        # Try unknown-department fallback
        if dept and 'unknown-department' in self.registry.get('fallback', {}):
            return self.registry['fallback']['unknown-department']
        
        # Last resort
        return 'general-agent'
    
    def get_agent_info(self, agent_name):
        """Get agent information (for logging/metrics)"""
        # In a more advanced version, this could look up agent metadata
        return {
            'name': agent_name,
            'script_path': f"./agents/{agent_name}/worker.py",
            'description': f"{agent_name.replace('-', ' ').title()} agent"
        }
    
    def list_mappings(self):
        """List all registry mappings (for debugging)"""
        mappings = []
        for dept, dept_map in self.registry.items():
            if dept not in ['fallback', 'user_overrides']:
                for task_type, agent in dept_map.items():
                    mappings.append({
                        'department': dept,
                        'type': task_type,
                        'agent': agent
                    })
        return mappings


def main():
    """CLI for testing the router"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test simple hub router')
    parser.add_argument('--task-id', type=int, help='Task ID (for context)')
    parser.add_argument('--department', help='Department (e.g., sales, eng)')
    parser.add_argument('--type', help='Task type (e.g., email-draft, bug-triage)')
    parser.add_argument('--user-id', help='User ID for override testing')
    parser.add_argument('--list', action='store_true', help='List all mappings')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    router = SimpleHubRouter()
    
    if args.list:
        mappings = router.list_mappings()
        if args.json:
            print(json.dumps(mappings, indent=2, ensure_ascii=False))
        else:
            print("📋 Agent Registry Mappings:")
            print("-" * 60)
            for m in mappings:
                print(f"{m['department']:15} | {m['type']:25} → {m['agent']}")
        return 0
    
    # Build task dict
    task = {}
    if args.department:
        task['department'] = args.department
    if args.type:
        task['type'] = args.type
    if args.user_id:
        task['user_id'] = args.user_id
    
    if not task:
        print("❌ Please provide at least --department or --type", file=sys.stderr)
        return 1
    
    agent = router.route_task(task)
    
    if args.json:
        result = {
            'task': task,
            'selected_agent': agent,
            'agent_info': router.get_agent_info(agent)
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"🎯 Selected agent: {agent}")
        if task:
            print(f"   Based on: {task}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())