"""Verify a staging API using two Firebase sessions and retained synthetic data.

Uses two recent ID tokens from environment variables, creates one Architecture
topic and two task runs, and signs out. Live mode can make two billable AI calls.
No credentials, response bodies, or model output are written to evidence.
"""
import argparse
import json
import os
import sys
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


class VerificationError(Exception):
    """An API contract did not meet the collaboration acceptance criteria."""


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def request(client, method, path, payload=None, expected=200):
    response = client.request(method, path, json=payload)
    require(response.status_code == expected,
            f'{method} {path}: expected HTTP {expected}, received {response.status_code}.')
    try:
        result = response.json()
    except ValueError as exc:
        raise VerificationError(f'{method} {path}: expected JSON.') from exc
    require(isinstance(result, dict), f'{method} {path}: expected a JSON object.')
    return result


def sign_in(client, token):
    config = request(client, 'GET', '/api/auth/config')
    client.headers.update({'X-ContextOS-Client': 'workspace',
                           'X-ContextOS-CSRF': config['csrf_token']})
    request(client, 'POST', '/api/auth/session', {'id_token': token})
    return request(client, 'GET', '/api/workspace')


def source_from(run, context_id):
    source = next((item for item in run['manifest']['sources']
                   if item['id'] == context_id), None)
    require(source is not None, 'The task did not retrieve the shared verification topic.')
    return source


def sign_out(client):
    # A connectivity failure during cleanup must not hide the original failure.
    try:
        client.post('/api/auth/logout', json={})
    except httpx.HTTPError:
        pass


def verify(client_factory, author_token, reviewer_token, *, allow_offline=False):
    """Exercise public API contracts; injectable HTTP clients keep tests local."""
    with client_factory() as author, client_factory() as reviewer:
        health = request(author, 'GET', '/api/health')
        require(health.get('auth_mode') == 'firebase', 'Firebase authentication is required.')
        ai_mode = health.get('ai_mode')
        require(ai_mode in ('vertex', 'gemini') or (allow_offline and ai_mode == 'offline'),
                'Live AI is required unless --allow-offline is explicitly selected.')
        request(author, 'GET', '/api/workspace', expected=401)
        try:
            first = sign_in(author, author_token)
            second = sign_in(reviewer, reviewer_token)
            require(first['actor'] != second['actor'], 'Two distinct user accounts are required.')
            require(first['role'] == 'developer' and second['role'] == 'architect',
                    'Use a Developer author and Architect reviewer in the same staging workspace.')

            title = f'Collaboration verification {uuid4().hex[:12]}'
            original = 'Retry transient provider failures up to 3 times. Preserve the idempotency key.'
            updated = original.replace('3 times', '2 times')
            proposal = request(author, 'POST', '/api/proposals', {
                'title': title, 'domain': 'Architecture', 'body': original,
                'reason': 'Synthetic collaboration verification.',
                'sources': ['Staging verification fixture'],
            })
            shared = request(reviewer, 'GET', '/api/workspace')
            require(any(p['id'] == proposal['id'] and p['status'] == 'pending'
                        for p in shared['proposals']),
                    'The reviewer cannot see the proposal; verify shared workspace membership.')
            review_path = f'/api/proposals/{proposal["id"]}/review'
            decision = {'hash': proposal['hash'], 'decision': 'approve'}
            request(author, 'POST', review_path, decision, expected=403)
            published = request(reviewer, 'POST', review_path, decision)
            context_id = published['published_context_id']

            # The second user's task consumes the author's accepted knowledge.
            task = {'query': f'{title}: plan payment retries and idempotency', 'budget': 16000}
            initial = request(reviewer, 'POST', '/api/tasks', task)
            require(initial['usage']['provider'] == ai_mode,
                    'The task provider does not match the configured AI mode.')
            source = source_from(initial, context_id)
            require(source['revision'] == 1 and source['body'] == original,
                    'The first task did not use the exact accepted v1 body.')

            change = request(author, 'POST', '/api/proposals', {
                'context_id': context_id, 'base_revision': 1, 'body': updated,
                'reason': 'Verify source-change propagation.',
                'sources': ['Staging verification fixture'],
            })
            request(reviewer, 'POST', f'/api/proposals/{change["id"]}/review',
                    {'hash': change['hash'], 'decision': 'approve'})
            current = request(reviewer, 'GET', '/api/workspace')
            publications = [event for event in current['events']
                            if event['context_id'] == context_id and event['action'] == 'Revision published']
            require(len(publications) == 2 and all(event['actor'] == second['actor'] for event in publications),
                    'Both publications must have attributable reviewer audit events.')
            old = next(run for run in current['tasks'] if run['id'] == initial['id'])
            require(old['stale'] and source_from(old, context_id) == source,
                    'The old run must be stale and retain its exact v1 source snapshot.')
            refreshed = request(reviewer, 'POST', '/api/tasks', task)
            require(refreshed['usage']['provider'] == ai_mode,
                    'The refreshed task provider does not match the configured AI mode.')
            latest = source_from(refreshed, context_id)
            require(latest['revision'] == 2 and latest['body'] == updated and not refreshed['stale'],
                    'The refreshed task did not adopt the exact accepted v2 body.')

            # A fresh session proves visibility beyond the original client's cookies.
            request(author, 'POST', '/api/auth/logout', {})
            request(author, 'GET', '/api/workspace', expected=401)
            with client_factory() as returning:
                try:
                    restored = sign_in(returning, author_token)
                    topic = next(c for c in restored['contexts'] if c['id'] == context_id)
                    require(topic['revision'] == 2 and len(topic['history']) == 2,
                            'A fresh session did not retain accepted revision history.')
                    require({initial['id'], refreshed['id']} <= {t['id'] for t in restored['tasks']},
                            'A fresh session did not retain shared task history.')
                finally:
                    sign_out(returning)
            request(reviewer, 'POST', '/api/auth/logout', {})
            request(reviewer, 'GET', '/api/workspace', expected=401)
            return {'context_id': context_id, 'accepted_revision': 2,
                    'initial_run_id': initial['id'], 'refreshed_run_id': refreshed['id'],
                    'ai_mode': ai_mode, 'offline_rehearsal': ai_mode == 'offline'}
        finally:
            # Best-effort logout must never hide the original verification failure.
            for client in (author, reviewer):
                sign_out(client)


def staging_url(value):
    parsed = urlsplit(value)
    local = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')
    if (not parsed.hostname or parsed.scheme != 'https' and not local
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise argparse.ArgumentTypeError('Use an HTTPS origin or a loopback HTTP origin without credentials.')
    return value.rstrip('/')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, type=staging_url)
    parser.add_argument('--allow-offline', action='store_true',
                        help='Explicit rehearsal only; never evidence of live AI.')
    args = parser.parse_args(argv)
    author_token = os.getenv('CONTEXTOS_AUTHOR_ID_TOKEN', '')
    reviewer_token = os.getenv('CONTEXTOS_REVIEWER_ID_TOKEN', '')
    if not author_token or not reviewer_token:
        parser.error('Set CONTEXTOS_AUTHOR_ID_TOKEN and CONTEXTOS_REVIEWER_ID_TOKEN securely in the environment.')
    try:
        result = verify(lambda: httpx.Client(base_url=args.base_url, timeout=60, follow_redirects=False),
                        author_token, reviewer_token, allow_offline=args.allow_offline)
    except VerificationError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    except Exception:
        print('FAIL: Verification could not complete. Check connectivity, configuration, and server logs.', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    print('PASS: shared decisions, independent review, v1/v2 snapshots, stale work, fresh sessions and logout.')
    print('Synthetic records are retained. This does not verify redeployment, backups or browser UI.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
