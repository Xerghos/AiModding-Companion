#!/usr/bin/env python
import sys
sys.path.insert(0, '.')
from ai_core.code_assist_converter import to_generate_content_request

messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': 'Hello!'},
    {'role': 'assistant', 'content': 'Hi there!'},
    {'role': 'user', 'content': 'List your tools'}
]

payload = to_generate_content_request('gemini-3-flash-preview', messages)

print('Contents count:', len(payload['request']['contents']))
for i, c in enumerate(payload['request']['contents']):
    print(f"  Content {i}: role={c['role']}")

si = payload['request'].get('systemInstruction', {})
print('SystemInstruction role:', si.get('role'))
print('GenerationConfig:', payload['request'].get('generationConfig'))
print('Session ID:', repr(payload['request'].get('session_id')))

# Validation
all_ok = True
if len(payload['request']['contents']) == 0:
    print('ERROR: contents is empty!')
    all_ok = False
if si.get('role') != 'user':
    print('ERROR: systemInstruction.role should be user!')
    all_ok = False
if 'maxOutputTokens' in payload['request'].get('generationConfig', {}):
    print('ERROR: maxOutputTokens should NOT be present!')
    all_ok = False

if all_ok:
    print('ALL CHECKS PASSED!')

