async function apiFetch(...args) {
  const response = await fetch(...args);
  if(response.status === 401) { window.location.assign('/'); throw new Error('Please sign in to continue.'); }
  return response;
}
const $ = id => document.getElementById(id);
let upload = null, ready = false, busy = false, localUrl = null, jobId = null, pollTimer = null, startedAt = null, preflight = null;
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
let uploading = false;
let completedVideo = null;
let saveRequest = null;
let shareFile = null;
let saveMethod = null;

function updateButton() {
  $('generate').disabled = !upload || !ready || busy || uploading;
  $('generate-label').textContent = busy ? 'Generating video…' : 'Generate video';
  $('view-result').hidden = !completedVideo;
  const step = busy ? 'generate' : completedVideo ? 'save' : upload ? 'generate' : 'upload';
  for (const name of ['upload', 'generate', 'save']) {
    const item = $('step-' + name);
    if (name === step) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  }
  $('next-settings').hidden = !upload || busy || uploading || Boolean(completedVideo);
  const note = uploading ? 'Uploading your clip…'
    : busy ? 'Your video is processing. Keep this tab open.'
    : completedVideo ? 'Your video is ready in step 3.'
    : !upload ? 'Upload a video first.'
    : !ready ? 'Open setup to check your engine.'
    : 'Ready to generate with the settings above.';
  if ($('generate-note').textContent !== note) $('generate-note').textContent = note;
}

function goTo(element) {
  element.focus({preventScroll: true});
  element.scrollIntoView({block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
}

$('next-settings').addEventListener('click', () => goTo($('generation-heading')));
$('view-result').addEventListener('click', () => goTo($('result-heading')));

function setSaveStatus(message) {
  $('save-status').textContent = message;
  $('save-status').hidden = !message;
}

function resetResult() {
  saveRequest?.abort();
  saveRequest = null;
  shareFile = null;
  completedVideo = null;
  $('save-actions').hidden = true;
  $('download').removeAttribute('href');
  $('output-video').pause();
  $('output-video').hidden = true;
  $('output-video').removeAttribute('src');
  $('output-video').load();
  $('result-placeholder').hidden = false;
  $('result-star').hidden = false;
  $('result-badge').textContent = 'THE BIG REVEAL';
  $('result-caption').textContent = 'Your original audio stays with the video.';
  $('progress-area').hidden = true;
  setSaveStatus('');
}

function showSaveOptions(videoUrl) {
  if (completedVideo === videoUrl) return;
  completedVideo = videoUrl;
  $('download').href = videoUrl + '?download=1';
  $('save-actions').hidden = false;
  const probe = new File([new Uint8Array([0])], 'bobhead.mp4', {type: 'video/mp4'});
  const canShare = typeof navigator.share === 'function' && navigator.canShare?.({files: [probe]});
  saveMethod = canShare ? 'share' : typeof window.showSaveFilePicker === 'function' ? 'picker' : null;
  $('save-video').hidden = !saveMethod;
  $('save-video').disabled = false;
  $('save-video').textContent = 'Save video';
  $('save-hint').textContent = saveMethod === 'share'
    ? 'Choose where to save in the share menu. On iPhone, look for Save Video or Save to Files.'
    : saveMethod === 'picker' ? 'Choose a filename and folder, or download the MP4.'
    : 'Find the MP4 in your browser’s Downloads. On a phone, open it and use Share to save it to Photos or Gallery if available.';
}

$('save-video').addEventListener('click', async () => {
  if (!completedVideo || saveRequest) return;
  const videoUrl = completedVideo;
  const request = new AbortController();
  const button = $('save-video');
  saveRequest = request;
  button.disabled = true;
  setSaveStatus('');
  try {
    // Open the picker directly from the tap, while browser activation is available.
    const handle = saveMethod === 'picker' ? await window.showSaveFilePicker({
      suggestedName: 'bobhead.mp4',
      types: [{description: 'MP4 video', accept: {'video/mp4': ['.mp4']}}],
    }) : null;
    if (request.signal.aborted) return;
    if (!shareFile) {
      setSaveStatus('Preparing your MP4…');
      const response = await apiFetch(videoUrl, {signal: request.signal});
      if (!response.ok) throw new Error('Could not load your video.');
      const blob = await response.blob();
      if (request.signal.aborted) return;
      shareFile = new File([blob], 'bobhead.mp4', {type: 'video/mp4'});
    }
    if (handle) {
      const writer = await handle.createWritable();
      try {
        await writer.write(shareFile);
        await writer.close();
      } catch (error) {
        await writer.abort().catch(() => {});
        throw error;
      }
      if (!request.signal.aborted) {
        setSaveStatus('Video saved.');
        shareFile = null;
      }
    } else {
      const data = {files: [shareFile]};
      if (!navigator.canShare(data)) throw new Error('File sharing is unavailable.');
      if (navigator.userActivation && !navigator.userActivation.isActive) {
        button.textContent = 'Open save options';
        setSaveStatus('Your video is ready. Tap Open save options to choose where to save it.');
        return;
      }
      await navigator.share(data);
      if (!request.signal.aborted) {
        shareFile = null;
        button.textContent = 'Save video';
        setSaveStatus('');
      }
    }
  } catch (error) {
    if (request.signal.aborted) return;
    if (error.name === 'NotAllowedError' && saveMethod === 'share' && shareFile && button.textContent !== 'Open save options') {
      button.textContent = 'Open save options';
      setSaveStatus('Tap Open save options to choose where to save your video.');
    } else {
      setSaveStatus(error.name === 'AbortError' ? '' : 'Use Download MP4 to save your video.');
    }
  } finally {
    if (saveRequest === request) {
      saveRequest = null;
      button.disabled = false;
    }
  }
});
function syncHeadSize() {
  const value = Number($('head-size').value);
  $('head-value').textContent = value.toFixed(1) + '×';
  $('hero-scale').textContent = value.toFixed(1) + '×';
  $('head-size').setAttribute('aria-valuetext', value.toFixed(1) + ' times head scale');
  $('head-size').style.setProperty('--range-fill', ((value - 1.2) / .8 * 100) + '%');
  document.documentElement.style.setProperty('--head-art', .75 + (value - 1.2) * .5);
  document.querySelectorAll('[data-head-size]').forEach(button => button.setAttribute('aria-pressed', Number(button.dataset.headSize) === value ? 'true' : 'false'));
}
$('head-size').addEventListener('input', syncHeadSize);
document.querySelectorAll('[data-head-size]').forEach(button => button.addEventListener('click', () => { if(busy) return; $('head-size').value = button.dataset.headSize; syncHeadSize(); }));
syncHeadSize();
async function checkEngine() {
  try {
    const response = await apiFetch('/api/preflight'); preflight = await response.json(); ready = preflight.ready;
    const cloud = preflight.backend === 'comfy-api';
    $('upload-hint').textContent = `MP4, MOV, WEBM · UP TO ${Math.round((preflight.max_upload_bytes || 256*1024*1024)/1024/1024)} MB`;
    if(cloud) { $('setup-help').textContent = 'Your video is processed on Comfy’s cloud GPU. There are no models to install on your computer. The first job after inactivity may wait for the cloud engine to start.'; $('privacy-note').textContent = 'Your clip is sent to Comfy’s cloud service. This demo removes its local copies of uploads and results after 24 hours; cloud-provider retention is separate. Only upload footage you have permission to share.'; }
    $('engine-button').className = `engine ${ready ? 'ready' : 'offline'}`;
    $('engine-label').textContent = cloud ? (ready ? 'Cloud connected' : 'Cloud unavailable') : ready ? 'Engine connected' : preflight.connected ? 'Setup needed' : 'Engine offline';
    const details = $('setup-details'); details.replaceChildren();
    const intro = document.createElement('p'); intro.textContent = preflight.connected ? `${preflight.workflow || 'BobHead workflow'} · ComfyUI ${preflight.comfy_version} · ${preflight.node_count} nodes. ${preflight.device}` : 'The engine is not connected.'; details.append(intro);
    if (preflight.issues?.length) { const list = document.createElement('ul'); preflight.issues.forEach(issue => { const li = document.createElement('li'); li.textContent = issue; list.append(li); }); details.append(list); }
    else { const p = document.createElement('p'); p.textContent = cloud ? 'Cloud credentials are connected. A completed generation is the final workflow check.' : 'Required node types and listed model selections are available. A generation is still the final check.'; details.append(p); }
  } catch (e) { ready = false; $('engine-label').textContent = 'App disconnected'; $('setup-details').textContent = 'Cannot reach the BobHead server. Restart the launcher.'; }
  updateButton();
}
async function chooseFile(file) {
  if (!file || busy || uploading) return;
  $('upload-followup').hidden = false;
  const uploadStatus = $('upload-status');
  uploadStatus.textContent = '';
  error('');
  const uploadLimit = preflight?.max_upload_bytes || 256*1024*1024;
  if (file.size > uploadLimit) { uploadStatus.textContent = `Choose a video smaller than ${Math.round(uploadLimit/1024/1024)} MB.`; return; }
  if (!/\.(mp4|mov|webm|mkv|avi)$/i.test(file.name)) { uploadStatus.textContent = 'Choose an MP4, MOV, WebM, MKV or AVI video.'; return; }
  uploading = true;
  upload = null;
  jobId = null;
  clearTimeout(pollTimer);
  localStorage.removeItem('bobhead-job');
  resetResult();
  updateButton();
  if(localUrl) URL.revokeObjectURL(localUrl); localUrl = URL.createObjectURL(file);
  $('input-video').src = localUrl; $('input-video').hidden = false; $('dropzone').hidden = true;
  $('input-name').textContent = file.name; $('input-badge').hidden = true; $('replace-button').hidden = false;
  $('input-time').textContent = `${(file.size/1024/1024).toFixed(1)} MB`;
  $('input-video').onloadedmetadata = () => { const d = $('input-video').duration; if(Number.isFinite(d)) $('input-time').textContent = `${d.toFixed(1)} sec`; };
  $('input-video').onerror = () => { error('Your browser cannot preview this format. Try an H.264 MP4 if playback is needed. ComfyUI may still be able to process it.'); };
  uploadStatus.textContent = 'Uploading your clip…';
  $('replace-button').disabled = true;
  const form = new FormData(); form.append('video', file);
  try {
    upload = await new Promise((resolve,reject) => { const xhr = new XMLHttpRequest(); xhr.open('POST','/api/uploads'); xhr.upload.onprogress = e => { if(e.lengthComputable) uploadStatus.textContent = `Uploading clip · ${Math.round(e.loaded/e.total*100)}%`; }; xhr.onload = () => { try { const data = JSON.parse(xhr.responseText); if(xhr.status >= 400) reject(new Error(data.error || 'Upload failed')); else resolve(data); } catch { reject(new Error('Upload failed. Check that BobHead and ComfyUI are running.')); } }; xhr.onerror = () => reject(new Error('Upload disconnected. Please try again.')); xhr.send(form); });
    uploadStatus.textContent = 'Video uploaded. Next, review the settings and generate.';
  } catch(e) {
    uploadStatus.textContent = e.message + ' Use Change video to try again.';
  } finally {
    uploading = false;
    $('replace-button').disabled = busy;
    updateButton();
  }
}
$('file-input').addEventListener('change', e => { chooseFile(e.target.files[0]); e.target.value = ''; });
$('replace-button').addEventListener('click', () => $('file-input').click());
$('dropzone').addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('file-input').click(); } });
['dragenter','dragover'].forEach(name => $('dropzone').addEventListener(name,e => { e.preventDefault(); $('dropzone').classList.add('dragging'); }));
['dragleave','drop'].forEach(name => $('dropzone').addEventListener(name,e => { e.preventDefault(); $('dropzone').classList.remove('dragging'); }));
$('dropzone').addEventListener('drop', e => chooseFile(e.dataTransfer.files[0]));
function setBusy(value) { busy = value; document.querySelectorAll('[data-head-size]').forEach(button => button.disabled = value); ['duration','prompt','head-size','file-input','replace-button'].forEach(id => $(id).disabled = value); updateButton(); }
function showJob(job) {
  if(!localUrl && job.input_url) {
    $('input-video').src = job.input_url; $('input-video').hidden = false; $('dropzone').hidden = true;
    $('input-name').textContent = job.input_name || 'Your clip'; $('input-badge').hidden = true; $('replace-button').hidden = false;
    localUrl = job.input_url; upload = {upload_id:job.upload_id};
    if(job.options) { $('duration').value = job.options.duration; $('head-size').value = job.options.head_size ?? 1.7; syncHeadSize(); $('prompt').value = job.options.prompt || ''; }
  }
  $('progress-area').hidden = false; if ($('stage').textContent !== job.stage) $('stage').textContent = job.stage;
  $('cancel-job').hidden = preflight?.backend !== 'comfy-api' || ['complete','error','cancelled','unknown'].includes(job.status);
  startedAt = job.created * 1000; const seconds = Math.floor(((job.completed ? job.completed*1000 : Date.now())-startedAt)/1000); $('elapsed').textContent = `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
  if(job.step?.max > 0) { $('step-progress').value = job.step.value; $('step-progress').max = job.step.max; $('progress-note').textContent = `Current stage · step ${job.step.value} of ${job.step.max}. Generation can take several minutes.`; }
  else { $('step-progress').removeAttribute('value'); $('progress-note').textContent = job.status === 'queued' ? 'Your clip is waiting in the engine’s queue.' : 'The engine is working. This can take several minutes.'; }
  if(job.status === 'unknown') { error(job.error); $('progress-note').textContent = 'New submissions are paused while the app owner checks the cloud job.'; setBusy(true); $('spinner').hidden = true; return false; }
  if(job.status === 'complete') {
    $('result-placeholder').hidden = true; $('output-video').hidden = false;
    const videoUrl = `/api/jobs/${job.id}/video`; if($('output-video').getAttribute('src') !== videoUrl) $('output-video').src = videoUrl;
    showSaveOptions(videoUrl); $('result-star').hidden = true;
    $('result-caption').textContent = 'Made it big.'; $('result-badge').textContent = 'READY TO SHARE';
    $('spinner').hidden = true; $('step-progress').value = 1; $('step-progress').max = 1;
    $('progress-note').textContent = 'Your BobHead is ready. Play it back and save it in step 3.';
    setBusy(false); return false;
  }
  if(['error','cancelled'].includes(job.status)) { $('spinner').hidden = true; $('progress-area').hidden = true; error(job.error || 'Generation stopped.'); setBusy(false); return false; }
  setBusy(true); $('spinner').hidden = false; return true;
}
async function poll() {
  if(!jobId) return;
  const requestedJob = jobId;
  try { const response = await apiFetch('/api/jobs/'+requestedJob); if (jobId !== requestedJob) return; if(response.status === 404 && !new URLSearchParams(location.search).has('job')) { localStorage.removeItem('bobhead-job'); jobId = null; return; } if(!response.ok) throw new Error('Could not recover this generation. Check it in ComfyUI or upload a new clip.'); const job = await response.json(); if(jobId === requestedJob && showJob(job)) pollTimer = setTimeout(poll,1500); }
  catch(e) { if (jobId === requestedJob) { error(e.message); setBusy(false); } }
}
$('generate').addEventListener('click', async () => {
  if(!upload || busy || uploading || !ready) return;
  error(''); resetResult(); setBusy(true);
  $('result-badge').textContent = 'IN THE MAKING'; $('result-caption').textContent = 'Good things take a little rendering.'; $('result-star').hidden = false;
  try { const response = await apiFetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({upload_id:upload.upload_id,duration:Number($('duration').value),head_size:Number($('head-size').value),prompt:$('prompt').value})}); const job = await response.json(); if(!response.ok) throw new Error(job.error || 'Could not start generation'); jobId = job.id; localStorage.setItem('bobhead-job',jobId); showJob(job); poll(); }
  catch(e) { error(e.message); setBusy(false); }
});
$('how-button').addEventListener('click', () => $('info-dialog').showModal());
['engine-button','setup-button'].forEach(id => $(id).addEventListener('click', () => { $('setup-dialog').showModal(); checkEngine(); }));
document.querySelectorAll('.dialog-close').forEach(b => b.addEventListener('click',() => b.closest('dialog').close()));
$('recheck').addEventListener('click',checkEngine);
checkEngine();
jobId = new URLSearchParams(location.search).get('job') || localStorage.getItem('bobhead-job'); if(jobId) poll();

let modelTimer = null;
const gb = bytes => (bytes/1e9).toFixed(1) + ' GB';
async function checkModels(first=false) {
  clearTimeout(modelTimer);
  try {
    const r = await apiFetch('/api/models'); const state = await r.json();
    $('open-models').hidden = !state.enabled;
    if(!state.enabled) return;
    if(first && !state.complete) $('models-dialog').showModal();
    const list = $('model-list'); list.replaceChildren();
    state.models.forEach(m => {
      const row=document.createElement('div'); row.className='model-row';
      const link=document.createElement('a'); link.href=m.source_url.replace('/resolve/','/blob/'); link.target='_blank'; link.rel='noopener'; link.textContent=m.path.split('/').pop();
      const detail=document.createElement('small'); detail.textContent=`${m.installed ? '✓ Installed' : gb(m.bytes)} · models/${m.path}`;
      row.append(link,detail); list.append(row);
    });
    const count=state.models.filter(m=>m.installed).length;
    $('model-summary').textContent=state.complete ? `All ${state.models.length} main models are installed. You’re ready to create.` : `${count} of ${state.models.length} installed · ${gb(state.remaining_bytes)} left to download.`;
    $('model-progress').textContent=state.current ? `${state.downloaded >= (state.models.find(m=>m.path===state.current)?.bytes || Infinity) ? 'Verifying' : 'Downloading'} ${state.current.split('/').pop()} · ${gb(state.downloaded)}` : state.complete ? 'Setup complete. Close this window to get started.' : 'Start or resume whenever you’re ready.';
    const current=state.models.find(m=>m.path===state.current);
    $('model-bar').value=current ? state.downloaded/current.bytes : state.complete ? 1 : 0;
    $('model-error').hidden=!state.error; $('model-error').textContent=state.error || '';
    $('download-models').disabled=state.running || state.complete;
    $('download-models').textContent=count || state.models.some(m=>m.partial_bytes) ? 'Resume downloads' : 'Download required models';
    $('pause-models').hidden=!state.running;
    if(state.running) modelTimer=setTimeout(checkModels,1500);
    else if(state.complete) checkEngine();
  } catch(e) { $('model-error').hidden=false; $('model-error').textContent='Could not check downloads. Restart BobHead and try again.'; }
}
$('open-models').onclick=()=>{ $('setup-dialog').close(); $('models-dialog').showModal(); checkModels(); };
$('download-models').onclick=async()=>{ $('download-models').disabled=true; try { const r=await apiFetch('/api/models/download',{method:'POST'}); const data=await r.json(); if(!r.ok) throw new Error(data.error); await checkModels(); } catch(e) { $('model-error').hidden=false; $('model-error').textContent=e.message; $('download-models').disabled=false; } };
$('pause-models').onclick=async()=>{ await apiFetch('/api/models/pause',{method:'POST'}); checkModels(); };
$('check-models').onclick=()=>{ checkModels(); checkEngine(); };
checkModels(true);

$('cancel-job').onclick = async () => { if(!jobId) return; $('cancel-job').disabled = true; try { await apiFetch('/api/jobs/'+jobId+'/cancel',{method:'POST'}); } finally { $('cancel-job').disabled = false; } };
