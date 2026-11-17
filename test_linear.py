import asyncio
import os
import unittest
from unittest import mock

import httpx
from mcp.server.mcpserver.exceptions import ToolError

import server
from server import mcp

ENV = {'LINEAR_API_KEY': 'test-key'}


def call_tool() -> dict:
    result = asyncio.run(mcp.call_tool('list_linear_teams', {}))
    return result.structured_content


@mock.patch.dict(os.environ, ENV)
@mock.patch('server.httpx.post')
class ListLinearTeamsTest(unittest.TestCase):
    def test_returns_teams(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, json={'data': {'teams': {'nodes': [
            {'id': 't1', 'key': 'ENG', 'name': 'Engineering'},
            {'id': 't2', 'key': 'SUP', 'name': 'Support'},
        ]}}})

        self.assertEqual(call_tool(), {'teams': [
            {'id': 't1', 'key': 'ENG', 'name': 'Engineering'},
            {'id': 't2', 'key': 'SUP', 'name': 'Support'},
        ]})
        args, kwargs = post.call_args
        self.assertEqual(args[0], server.LINEAR_URL)
        self.assertEqual(kwargs['headers'], {'Authorization': 'test-key'})
        self.assertIn('teams', kwargs['json']['query'])

    def test_no_teams(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, json={'data': {'teams': {'nodes': []}}})
        self.assertEqual(call_tool(), {'teams': []})

    def test_missing_api_key(self, post: mock.Mock) -> None:
        with mock.patch.dict(os.environ, clear=True):
            with self.assertRaisesRegex(ToolError, 'LINEAR_API_KEY not set'):
                server.list_linear_teams()
        post.assert_not_called()

    def test_timeout(self, post: mock.Mock) -> None:
        post.side_effect = httpx.ReadTimeout('timed out')
        with self.assertRaisesRegex(ToolError, 'timeout contacting linear'):
            server.list_linear_teams()

    def test_connection_error(self, post: mock.Mock) -> None:
        post.side_effect = httpx.ConnectError('no route')
        with self.assertRaisesRegex(ToolError, 'error contacting linear: no route'):
            server.list_linear_teams()

    def test_unauthorized(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(401, text='bad key')
        with self.assertRaisesRegex(ToolError, 'unauthorized contacting linear: 401 bad key'):
            server.list_linear_teams()

    def test_server_error(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(500, text='oops')
        with self.assertRaisesRegex(ToolError, 'error contacting linear: 500 oops'):
            server.list_linear_teams()

    def test_non_json_reply(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, text='<html>not json</html>')
        with self.assertRaisesRegex(ToolError, 'non-json'):
            server.list_linear_teams()

    def test_graphql_error(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, json={'errors': [{'message': 'field not found'}]})
        with self.assertRaisesRegex(ToolError, 'error contacting linear: field not found'):
            server.list_linear_teams()


READY_DRAFT = {
    'team_key': 'eng',
    'title': 'Checkout fails on submit',
    'priority': 'P1',
    'description': 'Clicking pay shows a spinner forever.',
    'labels': ['bug', 'billing'],
    'reproduction_steps': '1. add item 2. click pay',
    'affected_account': 'acct_1234',
}

TEAM_AND_LABELS = httpx.Response(200, json={'data': {
    'teams': {'nodes': [{'id': 'team-1', 'key': 'ENG'}]},
    'issueLabels': {'nodes': [
        {'id': 'label-bug', 'name': 'Bug'},
        {'id': 'label-billing', 'name': 'billing'},
        {'id': 'label-feature', 'name': 'Feature'},
    ]},
}})

CREATED = httpx.Response(200, json={'data': {'issueCreate': {
    'success': True,
    'issue': {'id': 'issue-1', 'identifier': 'ENG-42', 'url': 'https://linear.app/x/issue/ENG-42'},
}}})


def create_issue(arguments: dict) -> dict:
    result = asyncio.run(mcp.call_tool('create_linear_issue', arguments))
    return result.structured_content


@mock.patch.dict(os.environ, ENV)
@mock.patch('server.httpx.post')
class CreateLinearIssueTest(unittest.TestCase):
    def test_creates_issue(self, post: mock.Mock) -> None:
        post.side_effect = [TEAM_AND_LABELS, CREATED]

        result = create_issue(READY_DRAFT)

        self.assertTrue(result['created'])
        self.assertEqual(result['issue'], {'id': 'issue-1', 'identifier': 'ENG-42', 'url': 'https://linear.app/x/issue/ENG-42'})
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args_list[0].kwargs['json']['variables'], {'key': 'eng'})
        issue_input = post.call_args_list[1].kwargs['json']['variables']['input']
        self.assertEqual(issue_input['teamId'], 'team-1')
        self.assertEqual(issue_input['title'], 'Checkout fails on submit')
        self.assertEqual(issue_input['priority'], 2)
        self.assertEqual(issue_input['labelIds'], ['label-bug', 'label-billing'])
        self.assertEqual(issue_input['description'], (
            'Clicking pay shows a spinner forever.'
            '\n\n## reproduction steps\n\n1. add item 2. click pay'
            '\n\n## affected account\n\nacct_1234'
        ))

    def test_priority_mapping(self, post: mock.Mock) -> None:
        for priority, expected in [('p0', 1), ('p1', 2), ('p2', 3), ('p3', 4)]:
            post.reset_mock()
            post.side_effect = [TEAM_AND_LABELS, CREATED]
            create_issue({**READY_DRAFT, 'priority': priority})
            self.assertEqual(post.call_args_list[1].kwargs['json']['variables']['input']['priority'], expected, priority)

    def test_no_reproduction_steps_section_when_absent(self, post: mock.Mock) -> None:
        post.side_effect = [TEAM_AND_LABELS, CREATED]
        draft = {**READY_DRAFT, 'labels': ['feature']}
        del draft['reproduction_steps']

        self.assertTrue(create_issue(draft)['created'])
        description = post.call_args_list[1].kwargs['json']['variables']['input']['description']
        self.assertNotIn('reproduction steps', description)
        self.assertIn('## affected account', description)

    def test_invalid_draft_creates_nothing(self, post: mock.Mock) -> None:
        result = create_issue({**READY_DRAFT, 'priority': 'urgent'})

        self.assertFalse(result['created'])
        self.assertIsNone(result['issue'])
        self.assertFalse(result['report']['ready_to_create'])
        self.assertIn('priority', result['report']['invalid_fields'])
        post.assert_not_called()

    def test_unknown_team(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, json={'data': {
            'teams': {'nodes': []},
            'issueLabels': {'nodes': []},
        }})
        with self.assertRaisesRegex(ToolError, "no linear team with key 'nope'"):
            server.create_linear_issue(**{**READY_DRAFT, 'team_key': 'nope'})
        self.assertEqual(post.call_count, 1)

    def test_label_missing_in_linear(self, post: mock.Mock) -> None:
        post.return_value = httpx.Response(200, json={'data': {
            'teams': {'nodes': [{'id': 'team-1', 'key': 'ENG'}]},
            'issueLabels': {'nodes': [{'id': 'label-bug', 'name': 'Bug'}]},
        }})
        with self.assertRaisesRegex(ToolError, r"labels not found in linear for team 'eng': \['billing'\]"):
            server.create_linear_issue(**READY_DRAFT)
        self.assertEqual(post.call_count, 1)

    def test_linear_reports_failure(self, post: mock.Mock) -> None:
        post.side_effect = [TEAM_AND_LABELS, httpx.Response(200, json={'data': {'issueCreate': {'success': False, 'issue': None}}})]
        with self.assertRaisesRegex(ToolError, 'linear did not create the issue'):
            server.create_linear_issue(**READY_DRAFT)


if __name__ == '__main__':
    unittest.main()
