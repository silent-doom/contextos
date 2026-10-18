# Temporary storage

This folder stores local Markdown for prototype development. **This local mirror is temporary. Cloud deployments read canonical Markdown directly from their Firestore workspace records.** The adapter is backend/data/storage.py.

Layout (directories are created when content is saved):

```text
storage/
└── projects/
    └── {project_id}/
        ├── contexts/{context_id}/versions/v000001-{content_hash}.md
        └── proposals/{proposal_id}/candidate.md
```

Each project has one directory directly under storage/projects; there is no workspace folder layer. The existing application store retains metadata and reviewed content copies for compatibility and hash verification. The API checks project access before passing authorized records to this adapter, reads Markdown from these files, and verifies it against the reviewed version. Changes still require proposals and independent approval; do not edit approved files directly.

Sample projects are synthetic demo data. Runtime Markdown is ignored by Git. Keep this directory between local restarts; no database configuration change is included. This adapter is local prototype storage, not shared storage for multiple server instances.

Cloud selection uses make_markdown_storage: FirestoreStore receives WorkspaceMarkdownStorage, which reads the bodies/revisions already persisted transactionally with metadata and review hashes. No local Markdown directory is required on Cloud Run. SQLite development retains the local immutable file mirror and its tamper checks.
