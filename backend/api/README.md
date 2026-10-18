# Shared knowledge API and MCP prototype

Backend code is grouped in backend/api (routes, models, Markdown rules, service and tests) and backend/mcp (agent tools and optional dependencies). HTTP URLs and application startup are unchanged.

Open the existing app at http://127.0.0.1:8000/knowledge after restarting it:

~~~powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
~~~

1. Select one existing project from the sidebar. Local mode loads projects from storage/ and never seeds samples or creates per-session projects. Use New project to explicitly create an empty project with name, type and description; your authenticated user ID becomes its admin.
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

Local demo project/context data is shared by local browser and MCP sessions through the same storage/ registry. If Firebase authentication is used locally, records retain their verified access scope in that registry. Production Firestore records remain scoped to the host's verified identity; membership/roles never come from request fields. This prototype has no per-project invitations or private-document policies. Existing authentication, restricted knowledge and agent workflows remain in their original API.

Updates replace the context fields and require expected_version. Review requires the exact proposal hash, covering content, metadata, relationships and dependency versions. Competing accepted revisions or changed dependencies produce HTTP 409. Rejection leaves accepted content unchanged.

Both outgoing depends_on and references relationships affect freshness and downstream impact, including transitively. When a linked context publishes a new approved version, its consumers show **Requires review** in the map, context list and reader. Unchanged contexts show **Up to date**. Pending/rejected proposals do not change freshness. Review the affected content and approve an update (even if its text needs no change) to refresh its relationship baseline. Any other stale upstream links still require review. This measures approved revision freshness, not factual correctness. Cyclic dependencies and cross-project links are rejected; reference cycles terminate safely and a context's own revision is excluded from its upstream changes. Remove inbound links through approved updates before deleting a context. Deletion retains version history.

Current-context JSON responses (project contexts, list/search, read, graph, impact, status, sections and extraction) and their MCP tools include the same freshness fields:

~~~json
{"status":"stale","status_label":"Requires review","up_to_date":false,"requires_review":true,"changed_relationships":[{"source_id":"CTX-design","source_name":"System Architecture","target_id":"CTX-requirements","target_name":"Product Requirements","kind":"depends_on","reviewed_version":1,"current_version":2,"reason":"version_changed"}]}
~~~

status retains up_to_date/stale/deleted for existing clients. changed_relationships identifies each changed link, including an indirect source when the change is transitive; reason can also be missing, deleted or untracked. changed_dependencies remains a compatibility list of changed target IDs and now includes references. get_context_status also reports pending_proposals and optional known_version_current. Historical versions remain immutable snapshots, not current freshness reports. All freshness is calculated on reads; no database tables or migrations are added. Older dependency baselines remain valid; reference baselines are recovered from approved history at the context/proposal timestamp. If that evidence is unavailable, the context requires review rather than silently appearing current. Legacy proposal hashes and approved histories are preserved.

Local project/context data comes exclusively from storage/projects.json (project metadata, reviewed content copies, relationships, proposals, approvals and history) and storage/projects/{project_id}/ (proposal Markdown and immutable approved versions). Project IDs are server generated. Reads never regenerate missing files. Metadata commits use atomic file replacement after Markdown writes; an aborted commit can leave an unreferenced object. Content hashes prevent competing proposals from overwriting approved files. Local data is excluded from Git and never served as public static files. This prototype uses one local server process. Browser cookies do not partition or seed local projects.

When STORE_BACKEND=firestore or K_SERVICE is set, the project provider uses the existing Firestore transaction store for both metadata and Markdown. Production never uses storage/ or falls back to local files. This does not change database configuration or the other backend modules' storage.

Existing Markdown-only folders are listed with metadata_missing=true and their folder ID as the name. They remain read-only; restore the original project metadata to recover names, owners, relationships and approval history. Missing metadata is never inferred or published from raw Markdown.

No database provider, connection, schema or environment changes. Limits: 10 registered projects, 30 contexts/project including deleted history, 50 pending proposals/project and 12,000 UTF-8 bytes/context. Firestore retains the host's existing aggregate size cap. Uncatalogued folders do not count against the registered project limit.

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

Legacy sample creation: POST /projects/samples is disabled (409 locally, 403 outside demo mode). Startup and session changes never call it.

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

The MCP client keeps its authenticated session across calls. Local browser and MCP sessions discover the same saved projects. In Firebase mode, provide a valid token through the host's private CONTEXT_API_TOKEN environment; identities sharing verified workspace claims see the same projects. Tokens are never tool inputs or persisted. Only local API origins are supported.

The UI uses locally bundled Marked and DOMPurify; rendered Markdown is sanitized with a narrow tag/attribute allowlist. Images and executable/interactive HTML are excluded. Bundle versions and licenses are in web/vendor/README.md. No npm build is required.

Checks: python -m pytest -q tests backend/api/tests and node --test tests/browser_auth.test.cjs tests/browser_workspace.test.cjs backend/api/tests/context_pages.test.cjs. Project API tests use isolated local storage or an injected cloud-store double and include a real MCP stdio round trip. No live database changes are required.

Cloud deployments keep Markdown bodies and history in the same canonical Firestore transaction as project metadata and proposal hashes. No local Markdown directory is required in production.
