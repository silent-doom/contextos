// Keep the reviewed Voila walkthrough/narration; replace only the title cards.
const fs = require('fs'), {spawnSync} = require('child_process');
const ffmpeg = require(process.env.FFMPEG_MODULE || '/Users/faizanchoudhary/.npm/_npx/49e263e5a42648bf/node_modules/ffmpeg-static');
const review = JSON.parse(fs.readFileSync('.data/video-review.json'));
const duration = review.durationSec, ratio = 180 / duration;
const recipe = review.recipe;
recipe.durationSec = 180;
recipe.segments = recipe.segments.map(s => ({...s, at: +(s.at * ratio).toFixed(2)}));
recipe.postProcess = {durationSec: 180, playbackRate: duration / 180,
  titleCards: 'Original vector opening and closing artwork overlaid after Voila frame review; walkthrough and narration preserved'};
fs.writeFileSync('deliverables/demo/recipe.json', JSON.stringify(recipe, null, 2));
const filters = `[0:v][1:v]overlay=0:0:enable='lt(t,8.826)'[opening];[opening][2:v]overlay=0:0:enable='gte(t,196.3)',setpts=${ratio}*(PTS-STARTPTS)[video]`;
const args = ['-y', '-i', '.data/video-build/demo.mp4', '-loop', '1', '-i', 'deliverables/demo/opening.png', '-loop', '1', '-i', 'deliverables/demo/closing.png',
  '-filter_complex', filters, '-map', '[video]', '-map', '0:a', '-af', `atempo=${duration / 180},apad`, '-t', '180', '-r', '30',
  '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
  '-map_metadata', '-1', '-metadata', 'comment=voila-recipe:' + JSON.stringify(recipe), 'deliverables/demo/ContextOS-Demo.mp4'];
const result = spawnSync(ffmpeg, args, {encoding: 'utf8', maxBuffer: 8e6});
fs.writeFileSync('.data/video-build/finalize.log', result.stderr);
if (result.status !== 0) throw Error(result.stderr.slice(-2000));
// Export the actual encoded first frame as the preview, rather than a mockup.
const preview = spawnSync(ffmpeg, ['-y', '-i', 'deliverables/demo/ContextOS-Demo.mp4', '-frames:v', '1', 'deliverables/demo/preview.png'], {encoding:'utf8'});
if (preview.status !== 0) throw Error(preview.stderr.slice(-1000));
console.log('Three-minute narrated MP4 and encoded-frame preview exported.');
