# Markdown browser bundles

Self-hosted, pinned bundles from the official npm distributions. No build step.

- [Marked 18.1.1](https://www.npmjs.com/package/marked/v/18.1.1): lib/marked.umd.js saved as marked.js; MIT license in marked-LICENSE.
- [DOMPurify 3.4.16](https://www.npmjs.com/package/dompurify/v/3.4.16): dist/purify.min.js saved as purify.js; license in dompurify-LICENSE (Apache-2.0 or MPL-2.0).

context-pages.js sanitizes the parsed Markdown with a narrow tag/attribute allowlist. Raw document content cannot add UI action attributes, scripts, images, forms, or styles.