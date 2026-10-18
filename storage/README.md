# Temporary storage

This folder is the local source of truth for project/context data. **Local storage is temporary; production uses Firestore.** The providers are backend/data/projects.py and backend/data/storage.py.

Layout (directories are created when content is saved):

```text
storage/
├── projects.json                       # Names, owners, relationships, proposals, approvals and history
└── projects/
    └── {project_id}/
        ├── contexts/{context_id}/versions/v000001-{content_hash}.md
        └── proposals/{proposal_id}/candidate.md
```

Each project has one directory directly under storage/projects; there is no workspace folder layer. Local APIs and MCP tools load this registry and the Markdown files, independent of browser sessions. Restarts do not reset projects. Listing projects, opening a new session, or reading content does not create projects, sample data or missing Markdown files. Only explicit create/update/review operations write data. Changes still require proposals and independent approval; do not edit approved files directly.

Older project folders containing only Markdown remain visible with metadata_missing=true. Their original names, owners, relationships and approval history cannot be reconstructed from Markdown alone. They stay read-only until their original metadata is restored into projects.json. No approvals or owners are invented, and existing files are preserved.

Firestore mode is selected by the existing STORE_BACKEND=firestore setting or Cloud Run's K_SERVICE environment. It uses the configured Firestore store for project records and Markdown, with the existing verified identity boundary; it never reads/writes this folder or falls back to it after a cloud failure. No database configuration or schema is changed.

Local demo sessions share the registry. If Firebase authentication is used locally, the registry preserves the verified access scope for each project; it is not taken from request fields. Local registry updates use a process-wide lock and atomic file replacement; this prototype runs in a single local server process. Runtime data is ignored by Git. Keep this directory between restarts.
