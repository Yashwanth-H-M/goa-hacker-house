const elements = {
  form: document.querySelector('#query-form'),
  question: document.querySelector('#question'),
  generate: document.querySelector('#generate'),
  language: document.querySelector('#language'),
  submit: document.querySelector('#submit-button'),
  record: document.querySelector('#record-button'),
  recordLabel: document.querySelector('#record-label'),
  recordingStatus: document.querySelector('#recording-status'),
  systemStatus: document.querySelector('#system-status'),
  indexCount: document.querySelector('#index-count'),
  configuration: document.querySelector('#configuration-note'),
  resultPanel: document.querySelector('#result-panel'),
  resultTitle: document.querySelector('#result-title'),
  resultBadges: document.querySelector('#result-badges'),
  emptyState: document.querySelector('#empty-state'),
  responseContent: document.querySelector('#response-content'),
  transcript: document.querySelector('#transcript'),
  answer: document.querySelector('#answer'),
  metrics: document.querySelector('#metrics'),
  sourceCount: document.querySelector('#source-count'),
  sourceList: document.querySelector('#source-list'),
  deploymentStatus: document.querySelector('#deployment-status'),
};

const configuredApiBaseUrl = String(window.CONTEXTLINE_API_BASE_URL || '').replace(/\/$/, '');
const isLocalPythonOrigin = ['127.0.0.1', 'localhost', '::1'].includes(window.location.hostname);
const apiBaseUrl = configuredApiBaseUrl || (isLocalPythonOrigin ? '' : null);

function apiUrl(path) {
  if (apiBaseUrl === null) {
    throw new Error('The live retrieval API has not been connected to this frontend yet.');
  }
  return `${apiBaseUrl}${path}`;
}

let mediaRecorder = null;
let activeStream = null;
let audioChunks = [];
let recordingTimer = null;
let recordingStartedAt = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function setLoading(isLoading, message = 'Searching grounded context…') {
  elements.submit.disabled = isLoading;
  elements.record.disabled = isLoading;
  elements.submit.querySelector('span').textContent = isLoading ? 'Working…' : 'Ask the corpus';
  if (isLoading) {
    showWorking(message);
  }
}

function showWorking(message) {
  elements.resultPanel.classList.remove('is-empty');
  elements.emptyState.hidden = false;
  elements.responseContent.hidden = true;
  elements.emptyState.innerHTML = `<div class="empty-orbit" aria-hidden="true"><span></span></div><p>${escapeHtml(message)}</p>`;
  elements.resultTitle.textContent = 'Working through the pipeline';
  elements.resultBadges.innerHTML = '<span class="badge">IN PROGRESS</span>';
}

function showError(message) {
  elements.resultPanel.classList.remove('is-empty');
  elements.emptyState.hidden = false;
  elements.responseContent.hidden = true;
  elements.emptyState.innerHTML = `<div class="empty-orbit" aria-hidden="true"><span></span></div><p>${escapeHtml(message)}</p>`;
  elements.resultTitle.textContent = 'Request could not be completed';
  elements.resultBadges.innerHTML = '<span class="badge warn">CHECK CONFIGURATION</span>';
}

function setRecordingUi(isRecording) {
  elements.record.classList.toggle('is-recording', isRecording);
  elements.recordLabel.textContent = isRecording ? 'Stop recording' : 'Record voice';
  elements.question.disabled = isRecording;
  if (!isRecording) {
    elements.recordingStatus.textContent = 'Type a question or record up to 30 seconds of audio.';
  }
}

function formatMilliseconds(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(Number(value) < 10 ? 2 : 0)} ms`;
}

function renderResponse(response) {
  elements.resultPanel.classList.remove('is-empty');
  elements.emptyState.hidden = true;
  elements.responseContent.hidden = false;
  elements.resultTitle.textContent = response.refused ? 'Grounded refusal' : 'Response ready';

  const badgeMarkup = [
    `<span class="badge ${response.refused ? 'warn' : 'good'}">${response.refused ? 'REFUSED' : 'GROUNDED'}</span>`,
    `<span class="badge">${escapeHtml(String(response.path_taken || 'retrieval')).toUpperCase()}</span>`,
    `<span class="badge">${escapeHtml(String(response.language_display_name || response.language || 'corpus')).toUpperCase()}</span>`,
  ];
  if (response.generation_status) {
    badgeMarkup.push(`<span class="badge">GEN · ${escapeHtml(response.generation_status).toUpperCase()}</span>`);
  }
  if (response.guardrail_reason) {
    badgeMarkup.push(`<span class="badge warn">GUARD · ${escapeHtml(response.guardrail_reason).toUpperCase()}</span>`);
  }
  elements.resultBadges.innerHTML = badgeMarkup.join('');

  if (response.transcript) {
    elements.transcript.hidden = false;
    elements.transcript.textContent = response.transcript;
    elements.question.value = response.transcript;
  } else {
    elements.transcript.hidden = true;
  }

  elements.answer.textContent = response.answer || 'No answer content returned.';
  const timings = response.latency_ms || {};
  elements.metrics.innerHTML = [
    ['Confidence', `${Math.round(Number(response.confidence || 0) * 100)}%`],
    ['Retrieval', formatMilliseconds(timings.retrieval)],
    ['STT', formatMilliseconds(timings.stt)],
    ['Generation', formatMilliseconds(timings.generation)],
    ['Server E2E', formatMilliseconds(timings.api_end_to_end)],
    ['Browser E2E', formatMilliseconds(timings.client_end_to_end)],
  ].map(([label, value]) => `<span class="metric">${label}<strong>${value}</strong></span>`).join('');

  const sources = Array.isArray(response.retrieved_context) ? response.retrieved_context : [];
  elements.sourceCount.textContent = sources.length ? `${sources.length} chunks retrieved` : 'No source chunks cited';
  elements.sourceList.innerHTML = sources.map((source) => `
    <article class="source">
      <div class="source-meta"><span>${escapeHtml(source.chunk_id)}</span><span>RRF ${Number(source.rrf_score || 0).toFixed(4)}</span></div>
      <p class="source-text">${escapeHtml(source.text)}</p>
    </article>
  `).join('') || '<p class="source-text">No source passages are displayed for a refused or unavailable response.</p>';
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload?.error?.message || `Request failed with ${response.status}.`);
  }
  return payload;
}

async function submitText(question) {
  const startedAt = performance.now();
  const response = await fetch(apiUrl('/api/query'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language: elements.language.value, generate: elements.generate.checked, top_k: 5 }),
  });
  const payload = await parseResponse(response);
  payload.latency_ms = { ...(payload.latency_ms || {}), client_end_to_end: performance.now() - startedAt };
  return payload;
}

async function submitAudio(blob) {
  const startedAt = performance.now();
  const parameters = new URLSearchParams({ generate: String(elements.generate.checked), top_k: '5', language: elements.language.value });
  const response = await fetch(apiUrl(`/api/voice-query?${parameters.toString()}`), {
    method: 'POST',
    headers: {
      'Content-Type': blob.type || 'audio/webm',
      'X-Filename': 'browser-recording.webm',
    },
    body: blob,
  });
  const payload = await parseResponse(response);
  payload.latency_ms = { ...(payload.latency_ms || {}), client_end_to_end: performance.now() - startedAt };
  return payload;
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    throw new Error('This browser does not support in-browser audio recording.');
  }
  activeStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const supportedType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus'].find((type) => MediaRecorder.isTypeSupported(type));
  mediaRecorder = new MediaRecorder(activeStream, supportedType ? { mimeType: supportedType } : undefined);
  audioChunks = [];
  mediaRecorder.addEventListener('dataavailable', (event) => {
    if (event.data.size > 0) audioChunks.push(event.data);
  });
  mediaRecorder.addEventListener('stop', async () => {
    clearInterval(recordingTimer);
    activeStream?.getTracks().forEach((track) => track.stop());
    activeStream = null;
    setRecordingUi(false);
    const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
    if (!blob.size) {
      showError('No audio was captured. Please try recording again.');
      return;
    }
    setLoading(true, 'Transcribing voice, then retrieving evidence…');
    try {
      renderResponse(await submitAudio(blob));
    } catch (error) {
      showError(error.message || 'Voice query failed.');
    } finally {
      setLoading(false);
    }
  });
  mediaRecorder.start();
  recordingStartedAt = Date.now();
  setRecordingUi(true);
  recordingTimer = window.setInterval(() => {
    const elapsed = Math.floor((Date.now() - recordingStartedAt) / 1000);
    elements.recordingStatus.textContent = `Recording ${elapsed}s of 30s maximum…`;
    if (elapsed >= 30) stopRecording();
  }, 250);
}

function stopRecording() {
  if (mediaRecorder?.state === 'recording') {
    elements.recordingStatus.textContent = 'Preparing secure audio upload…';
    mediaRecorder.stop();
  }
}

function showFrontendOnlyState() {
  elements.systemStatus.className = 'system-status error';
  elements.systemStatus.lastElementChild.textContent = 'Frontend demo online · retrieval API not connected';
  elements.indexCount.textContent = 'CONNECT A PUBLIC PYTHON API TO ENABLE HINDI, KANNADA, AND TELUGU QUERIES';
  elements.deploymentStatus.textContent = 'PUBLIC FRONTEND DEMO · LIVE RETRIEVAL, VOICE, AND GENERATION REQUIRE THE PYTHON BACKEND';
  elements.submit.disabled = true;
  elements.record.disabled = true;
  elements.question.disabled = true;
  elements.generate.disabled = true;
  elements.language.disabled = true;
  elements.configuration.hidden = false;
  elements.configuration.querySelector('h2').textContent = 'The public retrieval backend has not been deployed yet.';
  elements.configuration.querySelector('p').innerHTML = 'This Vercel link publishes the Contextline interface. Deploy the Python service, then set <code>window.CONTEXTLINE_API_BASE_URL</code> in <code>web/app-config.js</code> to its public HTTPS URL before calling it a fully live RAG application.';
}

async function checkHealth() {
  if (apiBaseUrl === null) {
    showFrontendOnlyState();
    return;
  }
  try {
    const response = await fetch(apiUrl('/api/health'), { cache: 'no-store' });
    const health = await parseResponse(response);
    elements.systemStatus.className = 'system-status ready';
    elements.systemStatus.lastElementChild.textContent = apiBaseUrl ? 'Public retrieval ready' : 'Local retrieval ready';
    const languages = health.languages || {};
    const available = Object.keys(languages);
    for (const option of elements.language.options) {
      option.disabled = !available.includes(option.value);
    }
    if (!available.includes(elements.language.value) && available.length) {
      elements.language.value = available[0];
    }
    elements.indexCount.textContent = available.length
      ? available.map((language) => `${languages[language].display_name}: ${languages[language].chunks}`).join(' · ')
      : 'NO INDEXES READY';
    if (!health.providers.sarvam_stt || !health.providers.grounded_generation) {
      elements.configuration.hidden = false;
    }
  } catch (error) {
    elements.systemStatus.className = 'system-status error';
    elements.systemStatus.lastElementChild.textContent = 'Local service unavailable';
    elements.indexCount.textContent = '';
  }
}

elements.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const question = elements.question.value.trim();
  if (!question) return;
  setLoading(true);
  try {
    renderResponse(await submitText(question));
  } catch (error) {
    showError(error.message || 'Text query failed.');
  } finally {
    setLoading(false);
  }
});

elements.record.addEventListener('click', async () => {
  try {
    if (mediaRecorder?.state === 'recording') {
      stopRecording();
    } else {
      await startRecording();
    }
  } catch (error) {
    setRecordingUi(false);
    activeStream?.getTracks().forEach((track) => track.stop());
    activeStream = null;
    showError(error.message || 'Microphone access could not be started.');
  }
});

checkHealth();
