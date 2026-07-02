/* YouTube IFrame API + Transcript Sync */

let player = null;
let syncInterval = null;
let activeSegmentId = null;

// Called by YouTube IFrame API when ready
function onYouTubeIframeAPIReady() {
  player = new YT.Player('player', {
    videoId: window.YOUTUBE_VIDEO_ID,
    playerVars: {
      autoplay: 0,
      modestbranding: 1,
      rel: 0,
    },
    events: {
      onReady: onPlayerReady,
      onStateChange: onPlayerStateChange,
    },
  });
}

function onPlayerReady() {
  // Start sync polling
  syncInterval = setInterval(syncTranscript, 250);
}

function onPlayerStateChange(event) {
  // YT.PlayerState.PLAYING = 1
  if (event.data === 1 && !syncInterval) {
    syncInterval = setInterval(syncTranscript, 250);
  }
}

function syncTranscript() {
  if (!player || typeof player.getCurrentTime !== 'function') return;

  const currentTime = player.getCurrentTime();
  const segments = document.querySelectorAll('.segment[data-start]');
  let found = null;

  segments.forEach(seg => {
    const start = parseFloat(seg.dataset.start);
    const end = parseFloat(seg.dataset.end);
    if (currentTime >= start && currentTime < end) {
      found = seg;
    }
  });

  if (found && found.id !== activeSegmentId) {
    // Remove previous active
    if (activeSegmentId) {
      const prev = document.getElementById(activeSegmentId);
      if (prev) prev.classList.remove('segment--active');
    }
    // Set new active
    found.classList.add('segment--active');
    activeSegmentId = found.id;

    // Auto-scroll if enabled
    const toggle = document.getElementById('auto-scroll-toggle');
    if (toggle && toggle.checked) {
      found.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

// Click timestamp to seek video
function seekTo(seconds) {
  if (player && typeof player.seekTo === 'function') {
    player.seekTo(seconds, true);
    player.playVideo();
  }
}

// Inline text editing
function startEdit(id, textSpan) {
  const display = document.getElementById('text-display-' + id);
  const form = document.getElementById('text-form-' + id);
  if (display) display.style.display = 'none';
  if (form) {
    form.style.display = 'block';
    const textarea = form.querySelector('textarea');
    if (textarea) {
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    }
  }
}

function cancelEdit(id) {
  const display = document.getElementById('text-display-' + id);
  const form = document.getElementById('text-form-' + id);
  if (display) display.style.display = '';
  if (form) form.style.display = 'none';
}

// Handle Escape key for cancelling edits
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const openForm = document.querySelector('.segment-edit-form[style*="display: block"],.segment-edit-form[style*="display:block"]');
    if (openForm) {
      const id = openForm.id.replace('text-form-', '');
      cancelEdit(id);
    }
  }
});
