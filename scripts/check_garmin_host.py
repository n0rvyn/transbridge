"""Inspect Garmin discovery using a fresh instance of the selected desktop CLI.

This does not prove tools are available in an existing desktop conversation.
No Garmin data tools are called, and no conversation is created.
"""
import argparse
import json
import selectors
import subprocess
import time
from pathlib import Path


def inspect(executable):
    process = subprocess.Popen([str(executable), 'app-server'], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    sequence = 0

    def request(method, params):
        nonlocal sequence
        sequence += 1
        process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': sequence,
            'method': method, 'params': params})+'\n')
        process.stdin.flush()
        # A diagnostic timeout is not a claim that the host cannot load tools.
        deadline = time.monotonic()+50
        while time.monotonic() < deadline:
            if not selector.select(1):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError('Desktop diagnostic process exited before responding.')
            response = json.loads(line)
            if response.get('id') != sequence:
                continue
            if 'error' in response:
                raise RuntimeError(f'{method} returned an RPC error; discovery is unverified.')
            return response['result']
        raise TimeoutError(f'{method} observation timed out; discovery is unverified.')

    try:
        request('initialize', {'clientInfo': {'name': 'transbridge_diagnostic', 'version': '1.0'},
                              'capabilities': {'experimentalApi': True}})
        process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'initialized'})+'\n')
        process.stdin.flush()
        cursor = None
        cursors = set()
        matches = []
        while True:
            params = {'detail': 'toolsAndAuthOnly'}
            if cursor is not None:
                params['cursor'] = cursor
            result = request('mcpServerStatus/list', params)
            matches.extend(row for row in result['data']
                           if row.get('pluginId') == 'garminops@transbridge')
            cursor = result.get('nextCursor')
            if cursor is None:
                break
            if cursor in cursors:
                raise RuntimeError('Host repeated a pagination cursor; discovery is incomplete.')
            cursors.add(cursor)
        report = {'scope': 'fresh_desktop_app_server', 'current_chat_verified': False,
                  'servers': [{key: row.get(key) for key in
                    ('name', 'pluginId', 'runtimeStatus', 'toolsError')} |
                    {'tool_count': len(row.get('tools', {}))} for row in matches]}
        print(json.dumps(report), flush=True)
        if not matches or any(row.get('toolsError') or not row.get('tools') for row in matches):
            raise RuntimeError('Garmin tool discovery did not succeed.')
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', type=Path, required=True,
                        help='Path to the CLI bundled with the desktop being tested.')
    inspect(parser.parse_args().codex)
