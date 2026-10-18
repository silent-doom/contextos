# Shared knowledge API and MCP prototype

Backend code is grouped in backend/api (routes, models, Markdown rules, service and tests) and backend/mcp (agent tools and optional dependencies). HTTP URLs and application startup are unchanged.

Open the existing app at http://127.0.0.1:8000/knowledge after restarting it:

~~~powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
~~~

1. Create a project with name, type and description. Your authenticated user ID is the admin; the server records timestamps. Projects start empty.
2. Propose a context with a display name, a separate plain .md filename, Markdown, owner, owner type and optional relationships.
3. Open **Proposals**, inspect the proposed content and metadata, and approve as an independent reviewer with the designated owner role.
4. Read the approved Markdown and map. Edits and deletions use the same review flow.

For a demo: propose as Developer, choose owner type Architect, then switch the existing persona selector to Architect to approve. Project metadata edits/archive require its admin identity. Deleting a project archives it; use Project details to restore it.

## Shape and rules

Every Markdown file uses these fixed headings, in order. Content under them supports Markdown, tables and fenced code; use ### for subheadings.

~~~markdown
## Overview

## Details

## Next steps
~~~

Context records contain name, filename, content, owner, owner_type, relationships, version, creation/update timestamps and immutable approved history. The graph, reader and relationships show name; filename remains file metadata and the download filename. The UI requires a context name. Older API/MCP clients may omit name: creation derives a readable label, and updates keep the accepted name. Existing records are read with the same fallback; no migration is needed. Name changes require approval and are preserved in version history.

owner is a person/team label; owner_type selects the trusted reviewer role (pm, architect, developer, qa, security). A transfer requires the current owner role to review. The proposal author cannot decide their own proposal.

All projects in a workspace are readable by its authenticated members. Workspace membership/roles come from the host's verified identity, never request fields. This prototype has no per-project invitations or private-document policies. Existing restricted knowledge and legacy workflows remain in their original API.

Updates replace the context fields and require expected_version. Review requires the exact proposal hash, covering content, metadata, relationships and dependency versions. Competing accepted revisions or changed dependencies produce HTTP 409. Rejection leaves accepted content unchanged.

depends_on relationships affect freshness and downstream impact; references do not. A context is stale when an accepted dependency version changed, including transitively. This measures revision freshness, not whether the text is factually correct. Review and approve an update to refresh its dependency baseline. Cyclic dependencies and cross-project links are rejected. Remove inbound links through approved updates before deleting a context. Deletion retains version history.

The host's existing transactional store persists these records under context_projects in the workspace payload. No database provider, connection, schema, environment or migration changes. Limits: 10 projects/workspace, 30 contexts/project including deleted history, 50 pending proposals/project, 12,000 UTF-8 bytes/context, plus the host's existing aggregate size cap. No disk Markdown mirrors or runtime databases are added to the repository.

## HTTP and MCP

All paths below start with /api/context. IDs are server generated. Browser writes require X-ContextOS-Client: workspace and the host's same-origin checks.

| MCP tool | HTTP API |
|---|---|
| get_context_template | GET /template |
| discover_projects | GET /projects?include_archived=false |
| create_project | POST /projects |
| read_project | GET /projects/{project} |
| update_project | PUT /projects/{project} |
| archive_project | DELETE /projects/{project} |
| discover_context | GET /projects/{project}/contexts |
| search_context | GET /projects/{project}/search?q=words |
| create_context | POST /projects/{project}/contexts |
| read_context | GET /projects/{project}/contexts/{context} |
| update_context | PUT /projects/{project}/contexts/{context} |
| delete_context | DELETE /projects/{project}/contexts/{context} |
| read_context_sections | GET /projects/{project}/contexts/{context}/sections |
| extract_context | POST /projects/{project}/contexts/{context}/extract |
| get_context_status | GET /projects/{project}/contexts/{context}/status?known_version=1 |
| read_context_history | GET /projects/{project}/contexts/{context}/versions |
| read_context_version | GET /projects/{project}/contexts/{context}/versions/{version} |
| read_context_graph | GET /projects/{project}/graph |
| inspect_context_impact | GET /projects/{project}/impact/{context} |
| list_context_proposals | GET /projects/{project}/proposals |
| read_context_proposal | GET /projects/{project}/proposals/{proposal} |
| read_project_activity | GET /projects/{project}/activity |

UI review: POST /projects/{project}/proposals/{proposal}/review with {"hash":"exact SHA256","decision":"approve"} or reject. Approval is deliberately absent from the agent tool set. UI Markdown download: GET /projects/{project}/contexts/{context}/markdown.

List/search accept offset and limit (1–100). Read/extract accept bounded character limits (at most 12,000). Version lists omit old contents; request a specific version to read them.

New project:

~~~json
{"name":"ContextOS","project_type":"software","description":"Shared project context"}
~~~

New context (returns a pending proposal):

~~~json
{"name":"System Architecture","filename":"architecture.md","content":"## Overview\n\nShared service.\n\n## Details\n\nFastAPI.\n\n## Next steps\n\nReview the design.","owner":"Architecture team","owner_type":"architect","relationships":[],"reason":"Record the design"}
~~~

Update: same context fields plus expected_version. Delete: {"expected_version":1,"reason":"No longer needed"}. Project update: name, project_type, description, admin, expected_version and optional archived. Project deletion requires expected_version and reason.

## MCP setup

Install the existing app requirements and the optional MCP package:

~~~powershell
python -m pip install -r backend/mcp/requirements.txt
python backend/mcp/server.py
~~~

Host configuration (replace paths with your interpreter and checkout):

~~~json
{"mcpServers":{"contextos":{"command":"C:/path/to/contextos/.venv/Scripts/python.exe","args":["C:/path/to/contextos/backend/mcp/server.py"],"env":{"CONTEXT_API_URL":"http://127.0.0.1:8000"}}}}
~~~

The MCP client keeps one demo session across calls. Demo browser sessions are separate sandboxes, so their projects are separate from MCP's sandbox. In Firebase mode, provide a valid token through the host's private CONTEXT_API_TOKEN environment; identities sharing verified workspace claims see the same projects. Tokens are never tool inputs or persisted. Only local API origins are supported.

The UI uses locally bundled Marked and DOMPurify; rendered Markdown is sanitized with a narrow tag/attribute allowlist. Images and executable/interactive HTML are excluded. Bundle versions and licenses are in web/vendor/README.md. No npm build is required.

Checks: python -m pytest -q tests backend/api/tests and node --test tests/browser_auth.test.cjs backend/api/tests/context_pages.test.cjs. API tests use an isolated memory store and include a real MCP stdio round trip. No live database changes are required.
