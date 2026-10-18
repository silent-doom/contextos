"""Two synthetic projects for the local demo, added once per workspace."""
from backend.api import service as s


SAMPLES = [
    ('Checkout Reliability', 'Software', 'A sample payment checkout service with safe retries.', [
        ('Product Requirements', 'requirements.md', 'pm', [],
         'Customers must be charged once, even when a payment request is retried.',
         'Retry transient failures only. Declined cards are not retryable. Show a clear outcome to the customer.',
         'Review the payment flow and acceptance criteria.'),
        ('System Architecture', 'architecture.md', 'architect', [0],
         'The checkout API coordinates payment requests and records their outcomes.',
         'Use an idempotency key per purchase. Repeated requests return the original outcome. Keep provider calls behind one service boundary.',
         'Review failure handling and timeout behavior.'),
        ('Payment API', 'payment-api.md', 'developer', [1],
         'Submit payments through a single checkout endpoint.',
         'Validate the purchase and idempotency key. Record the outcome before returning success. Return actionable errors without exposing provider details.',
         'Implement the endpoint and request validation.'),
        ('Quality Checks', 'quality-checks.md', 'qa', [0, 2],
         'Verify that retries do not create duplicate charges.',
         'Test repeated keys, provider timeouts, declined cards and concurrent requests. Confirm stable responses and audit records.',
         'Run the checkout regression scenarios.'),
    ]),
    ('Research Assistant', 'Research', 'A sample research project with traceable sources and findings.', [
        ('Research Brief', 'research-brief.md', 'pm', [],
         'Study how teams maintain reliable shared knowledge.',
         'Compare approaches using source quality, review effort and update freshness. Separate evidence from assumptions.',
         'Agree on research questions and evaluation criteria.'),
        ('Source Catalog', 'source-catalog.md', 'architect', [0],
         'Track the evidence used by the research team.',
         'Record each source, its publication date and the claim it supports. Prefer primary sources and mark unresolved gaps.',
         'Collect an initial set of sources for review.'),
        ('Analysis Plan', 'analysis-plan.md', 'architect', [0, 1],
         'Compare evidence against the agreed research questions.',
         'Use the same evaluation criteria for every approach. Document uncertainty and retain references for each conclusion.',
         'Review the analysis method with the team.'),
        ('Findings Summary', 'findings.md', 'pm', [2],
         'Summarize the approved findings and their practical implications.',
         'Keep conclusions linked to evidence. Highlight limitations and follow-up questions instead of presenting assumptions as facts.',
         'Publish a reviewed summary after the analysis is complete.'),
    ]),
]


def create_samples(state, actor):
    if 'context_sample_projects' in state:
        return [s.metadata(s.project(state, pid)) for pid in state['context_sample_projects']]
    if len(s.projects(state)) + len(SAMPLES) > 10:
        from backend.domain import Problem
        raise Problem('There is no room for the two sample projects.', 409)
    ids = []
    for name, project_type, description, documents in SAMPLES:
        project = s.create_project(state, actor, {'name': name, 'project_type': project_type, 'description': description})
        item, contexts = s.project(state, project['id']), []
        for title, filename, role, dependencies, overview, details, next_steps in documents:
            proposal = s.propose(item, 'demo-sample-author', 'create', {
                'name': title, 'filename': filename,
                'content': f'## Overview\n\n{overview}\n\n## Details\n\n{details}\n\n## Next steps\n\n{next_steps}\n',
                'owner': title + ' team', 'owner_type': role,
                'relationships': [{'target_id': contexts[index], 'kind': 'depends_on'} for index in dependencies],
                'reason': 'Synthetic sample baseline for the prototype',
            })
            s.review(item, 'demo-sample-reviewer', role, proposal['id'], {'hash': proposal['hash'], 'decision': 'approve'})
            contexts.append(proposal['context_id'])
        ids.append(project['id'])
    state['context_sample_projects'] = ids
    return [s.metadata(s.project(state, pid)) for pid in ids]
