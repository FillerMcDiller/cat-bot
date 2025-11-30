#!/usr/bin/env python3
"""Extract all bot commands from main.py and export as JSON for bot websites."""

import re
import json

def extract_commands(filepath):
    """Extract all @bot.tree.command decorators and their function names."""
    commands = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match @bot.tree.command decorators and following function definitions
    # Matches: @bot.tree.command(name="...", description="...")
    # And: @bot.tree.command(description="...")
    pattern = r'@bot\.tree\.command\((.*?)\)\s*(?:@[^\n]*\n)*\s*(?:async\s+)?def\s+(\w+)'
    
    matches = re.finditer(pattern, content, re.DOTALL | re.MULTILINE)
    
    for match in matches:
        decorator_content = match.group(1)
        func_name = match.group(2)
        
        # Extract name if explicitly provided, otherwise use function name
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', decorator_content)
        if name_match:
            command_name = name_match.group(1)
        else:
            command_name = func_name
        
        # Extract description
        desc_match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', decorator_content)
        if desc_match:
            description = desc_match.group(1)
        else:
            description = "No description"
        
        commands.append({
            "name": command_name,
            "description": description,
            "type": 1  # Type 1 = Chat Input (slash command)
        })
    
    return commands

def main():
    # Extract from main.py
    commands = extract_commands('main.py')
    
    # Also check christmas_update.py if it has commands
    try:
        christmas_commands = extract_commands('christmas_update.py')
        commands.extend(christmas_commands)
    except FileNotFoundError:
        pass
    
    # Remove duplicates (keep first occurrence)
    seen = set()
    unique_commands = []
    for cmd in commands:
        if cmd['name'] not in seen:
            seen.add(cmd['name'])
            unique_commands.append(cmd)
    
    # Sort by name
    unique_commands.sort(key=lambda x: x['name'])
    
    # Export to JSON
    output = json.dumps(unique_commands, indent=2, ensure_ascii=False)
    
    # Print to console
    print(output)
    
    # Also save to file
    with open('commands.json', 'w', encoding='utf-8') as f:
        f.write(output)
    
    print(f"\n✅ Exported {len(unique_commands)} commands to commands.json", file=__import__('sys').stderr)

if __name__ == '__main__':
    main()
