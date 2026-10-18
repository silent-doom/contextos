# ContextOS hackathon deliverables

Team: **Three-Way Handshake** — Faizan Choudhary, Amogh Prabhu, Ankush Bhagat.

## Pitch

- `pitch/ContextOS-Pitch.pptx`: editable 14-slide landscape presentation adapted from the official hackathon template.
- `pitch/ContextOS-Pitch.pdf`: PDF exported from that PowerPoint, under the 5 MB submission limit.
- Content: problem, idea, differentiation, features, workflow, five personas, editable architecture, stack, operating costs/limits, actual prototype screenshot, verified evidence, SWOT, roadmap and access links.
- Fonts use Arial for portability; event artwork and source slide dimensions are preserved. Instruction/unused slides were removed. No productivity gains, production certification or load benchmark is claimed.

## Demo

- `demo/demo-prompt.md`: requested recording prompt with the deployed URL filled in.
- `demo/steps.yaml`: captions, narration and choreography for the public walkthrough.
- `demo/ContextOS-Demo.mp4`: exactly three minutes, narrated and captioned, recorded with Voila and reviewed twice. Raw recording frames and narration caches stay under ignored `.data/`.
- Public walkthrough uses synthetic data and offline source briefings; the separate protected team service has live verified Vertex AI and Firestore. The narration distinguishes these.
- For the submission form, publish the final MP4 to the permitted public video host and enter that share URL. No public video-host account was used automatically.

## Judge access

- Team workspace: https://contextos-443743777956.asia-south1.run.app
- Synthetic walkthrough: https://contextos-demo-443743777956.asia-south1.run.app
- A separate Developer member in `judges-mvp` has seeded checkout knowledge. Credentials are in the private local `.data/judge-access.txt` file, excluded from Git and all media. Share them only through the judging process.
- Start in Overview, use Work for a live grounded task, inspect exact sources, propose a change and inspect the pending Inbox. Member identity is fixed: self-approval and persona switching are denied. The public walkthrough demonstrates the independent reviewer and other personas; live two-user publication is separately verified in `deployment/verification.md`.
