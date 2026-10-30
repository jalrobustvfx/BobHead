const $ = id => document.getElementById(id);
let upload = null, ready = false, busy = false, localUrl = null, jobId = null, pollTimer = null, startedAt = null, preflight = null;
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function updateButton() { $('generate').disabled = !upload || !ready || busy; $('generate-note').textContent = busy ? 'Keep this tab open. Your video is on its way.' : !ready ? 'Connect your engine to generate.' : upload ? 'Ready when you are. Let’s make it big.' : 'Choose a clip to get started.'; }
async function checkEngine() {
  try {
    const response = await fetch('/api/preflight'); preflight = await response.json(); ready = preflight.ready;
    $('engine-button').className = `engine ${ready ? 'ready' : 'offline'}`;
    $('engine-label').textContent = ready ? 'Engine connected' : preflight.connected ? 'Setup needed' : 'Engine offline';
    const details = $('setup-details'); details.replaceChildren();
    const intro = document.createElement('p'); intro.textContent = preflight.connected ? `${preflight.workflow || 'BobHead workflow'} · ComfyUI ${preflight.comfy_version} · ${preflight.node_count} nodes. ${preflight.device}` : 'The engine is not connected.'; details.append(intro);
    if (preflight.issues?.length) { const list = document.createElement('ul'); preflight.issues.forEach(issue => { const li = document.createElement('li'); li.textContent = issue; list.append(li); }); details.append(list); }
    else { const p = document.createElement('p'); p.textContent = 'Required node types and listed model selections are available. A generation is still the final check.'; details.append(p); }
  } catch (e) { ready = false; $('engine-label').textContent = 'App disconnected'; $('setup-details').textContent = 'Cannot reach the BobHead server. Restart the launcher.'; }
  updateButton();
}
async function chooseFile(file) {
  if (!file || busy) return;
  error(''); upload = null; updateButton();
  if (file.size > 256*1024*1024) { error('Choose a video smaller than 256 MB.'); return; }
  if (!/\.(mp4|mov|webm|mkv|avi)$/i.test(file.name)) { error('Choose an MP4, MOV, WebM, MKV or AVI video.'); return; }
  if(localUrl) URL.revokeObjectURL(localUrl); localUrl = URL.createObjectURL(file);
  $('input-video').src = localUrl; $('input-video').hidden = false; $('dropzone').hidden = true;
  $('input-name').textContent = file.name; $('input-badge').hidden = true; $('replace-button').hidden = false;
  $('input-time').textContent = `${(file.size/1024/1024).toFixed(1)} MB`;
  $('input-video').onloadedmetadata = () => { const d = $('input-video').duration; if(Number.isFinite(d)) $('input-time').textContent = `${d.toFixed(1)} sec`; };
  $('input-video').onerror = () => { error('Your browser cannot preview this format. Try an H.264 MP4 if playback is needed. ComfyUI may still be able to process it.'); };
  $('generate-note').textContent = 'Uploading to your engine…';
  $('replace-button').disabled = true;
  const form = new FormData(); form.append('video', file);
  try {
    upload = await new Promise((resolve,reject) => { const xhr = new XMLHttpRequest(); xhr.open('POST','/api/uploads'); xhr.upload.onprogress = e => { if(e.lengthComputable) $('generate-note').textContent = `Uploading clip · ${Math.round(e.loaded/e.total*100)}%`; }; xhr.onload = () => { try { const data = JSON.parse(xhr.responseText); if(xhr.status >= 400) reject(new Error(data.error || 'Upload failed')); else resolve(data); } catch { reject(new Error('Upload failed. Check that BobHead and ComfyUI are running.')); } }; xhr.onerror = () => reject(new Error('Upload disconnected. Please try again.')); xhr.send(form); });
    if(jobId && !busy) { localStorage.removeItem('bobhead-job'); jobId = null; }
  } catch(e) { error(e.message); }
  $('replace-button').disabled = false; updateButton();
}
$('file-input').addEventListener('change', e => { chooseFile(e.target.files[0]); e.target.value = ''; });
$('replace-button').addEventListener('click', () => $('file-input').click());
$('dropzone').addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('file-input').click(); } });
['dragenter','dragover'].forEach(name => $('dropzone').addEventListener(name,e => { e.preventDefault(); $('dropzone').classList.add('dragging'); }));
['dragleave','drop'].forEach(name => $('dropzone').addEventListener(name,e => { e.preventDefault(); $('dropzone').classList.remove('dragging'); }));
$('dropzone').addEventListener('drop', e => chooseFile(e.dataTransfer.files[0]));
function setBusy(value) { busy = value; ['duration','prompt','file-input','replace-button'].forEach(id => $(id).disabled = value); updateButton(); }
function showJob(job) {
  if(!localUrl && job.input_url) {
    $('input-video').src = job.input_url; $('input-video').hidden = false; $('dropzone').hidden = true;
    $('input-name').textContent = job.input_name || 'Your clip'; $('input-badge').hidden = true; $('replace-button').hidden = false;
    localUrl = job.input_url; upload = {upload_id:job.upload_id};
    if(job.options) { $('duration').value = job.options.duration; $('prompt').value = job.options.prompt || ''; }
  }
  $('progress-area').hidden = false; $('stage').textContent = job.stage;
  startedAt = job.created * 1000; const seconds = Math.floor(((job.completed ? job.completed*1000 : Date.now())-startedAt)/1000); $('elapsed').textContent = `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
  if(job.step?.max > 0) { $('step-progress').value = job.step.value; $('step-progress').max = job.step.max; $('progress-note').textContent = `Current stage · step ${job.step.value} of ${job.step.max}. Generation can take several minutes.`; }
  else { $('step-progress').removeAttribute('value'); $('progress-note').textContent = job.status === 'queued' ? 'Your clip is waiting in the engine’s queue.' : 'The engine is working. This can take several minutes.'; }
  if(job.status === 'complete') {
    $('result-placeholder').hidden = true; $('output-video').hidden = false;
    const videoUrl = `/api/jobs/${job.id}/video`; if($('output-video').getAttribute('src') !== videoUrl) $('output-video').src = videoUrl;
    $('download').href = videoUrl+'?download=1'; $('download').hidden = false; $('result-star').hidden = true;
    $('result-caption').textContent = 'Made it big.'; $('result-badge').textContent = 'READY TO SHARE';
    $('spinner').hidden = true; $('step-progress').value = 1; $('step-progress').max = 1;
    $('progress-note').textContent = 'Press play to check the motion and original dialogue, then download your MP4.';
    setBusy(false); return false;
  }
  if(['error','cancelled'].includes(job.status)) { $('spinner').hidden = true; $('progress-area').hidden = true; error(job.error || 'Generation stopped.'); setBusy(false); return false; }
  setBusy(true); $('spinner').hidden = false; return true;
}
async function poll() {
  if(!jobId) return;
  try { const response = await fetch('/api/jobs/'+jobId); if(!response.ok) throw new Error('Could not recover this generation. Check it in ComfyUI or upload a new clip.'); const job = await response.json(); if(showJob(job)) pollTimer = setTimeout(poll,1500); }
  catch(e) { error(e.message); setBusy(false); }
}
$('generate').addEventListener('click', async () => {
  if(!upload || busy) return; error(''); setBusy(true);
  $('download').hidden = true; $('output-video').hidden = true; $('output-video').pause(); $('output-video').removeAttribute('src'); $('result-placeholder').hidden = false;
  $('result-badge').textContent = 'IN THE MAKING'; $('result-caption').textContent = 'Good things take a little rendering.'; $('result-star').hidden = false;
  try { const response = await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({upload_id:upload.upload_id,duration:Number($('duration').value),prompt:$('prompt').value})}); const job = await response.json(); if(!response.ok) throw new Error(job.error || 'Could not start generation'); jobId = job.id; localStorage.setItem('bobhead-job',jobId); showJob(job); poll(); }
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
    const r = await fetch('/api/models'); const state = await r.json();
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
    $('model-summary').textContent=state.complete ? 'All 12 main models are installed. You’re ready to create.' : `${count} of ${state.models.length} installed · ${gb(state.remaining_bytes)} left to download.`;
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
$('download-models').onclick=async()=>{ $('download-models').disabled=true; try { const r=await fetch('/api/models/download',{method:'POST'}); const data=await r.json(); if(!r.ok) throw new Error(data.error); await checkModels(); } catch(e) { $('model-error').hidden=false; $('model-error').textContent=e.message; $('download-models').disabled=false; } };
$('pause-models').onclick=async()=>{ await fetch('/api/models/pause',{method:'POST'}); checkModels(); };
$('check-models').onclick=()=>{ checkModels(); checkEngine(); };
checkModels(true);
