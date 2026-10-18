# Recording and finishing source

Use ../steps.yaml with Voila:

```sh
npx -y voila-recorder record https://contextos-demo-443743777956.asia-south1.run.app --steps deliverables/demo/steps.yaml --voice af_heart --speed 1.12 --keep-frames --out .data/video-build
```

The local finalize.cjs script corrects title contrast and paces the complete capture/narration to exactly three minutes. It references this workstation's cached Voila/FFmpeg path; update that path if reproducing elsewhere. It expects the raw Voila files and review JSON under .data/. No browser security policy was disabled. The final embedded/standalone recipe records the post-processing step.
