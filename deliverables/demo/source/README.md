# Recording and finishing source

Use ../steps.yaml with Voila:

```sh
npx -y voila-recorder record https://contextos-demo-443743777956.asia-south1.run.app --steps deliverables/demo/steps.yaml --voice af_heart --speed 1.12 --keep-frames --out .data/video-build
```

The local finalize.cjs script corrects title contrast and paces the complete capture/narration to exactly three minutes. It references this workstation's cached Voila/FFmpeg path; update that path if reproducing elsewhere. It expects the raw Voila files and review JSON under .data/. No browser security policy was disabled. The final embedded/standalone recipe records the post-processing step.

Regenerate the original vector cards with node deliverables/demo/source/title-cards.cjs, then run node deliverables/demo/source/finalize.cjs from the repository root. SHARP_MODULE and FFMPEG_MODULE can override cached module paths on another workstation. Opening/closing SVGs and PNGs are committed; private raw capture caches are not. The finalizer keeps the original Voila capture/audio and replaces only title cards, updates the embedded recipe and extracts the encoded first frame as preview.png.
