import asyncio
import json
import sys

from server import mcp


async def main() -> int:
    with open('samples.json') as f:
        samples = json.load(f)

    failures = 0
    for sample in samples:
        name = sample['name']
        expect = sample['expect']

        try:
            result = await mcp.call_tool('validate_issue_draft', sample['arguments'])
        except Exception as e:
            # the sdk rejected the input before the tool ran (schema error)
            if 'error' in expect:
                print(f'PASS | {name}')
            else:
                failures += 1
                print(f'FAIL | {name}\n   unexpected error: {e}')
            continue

        report = result.structured_content
        got = {
            'ready_to_create': report['ready_to_create'],
            'missing_fields': report['missing_fields'],
            'invalid_fields': list(report['invalid_fields']),
            'warning_count': len(report['warnings']),
        }

        if got == expect:
            print(f'PASS | {name}')
        else:
            failures += 1
            print(f'FAIL | {name}\n   got:      {got}\n   expected: {expect}')

    print(f'\n{len(samples) - failures}/{len(samples)} passed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
