# Pitch authoring source

Authored with the Codex bundled `@oai/artifact-tool` JavaScript API. The script imports the official template retrieved from the template URL in `hackathon.md`, keeps its dimensions and event artwork, and adds editable text, tables and diagrams. It references local runtime/build paths from this workstation; update those paths and provide the original template before rerunning elsewhere. The delivered PowerPoint is independently editable without this script.

Private validation records and temporary raster renders stay under `.data/pitch-build/`. Final PPTX and PDF are in the parent directory. The PDF was generated from the final PPTX with LibreOffice and every page was inspected. No PowerPoint application verification is claimed.
