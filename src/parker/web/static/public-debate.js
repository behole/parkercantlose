/* YouTube IFrame API + Transcript Sync (public read-only page) */

let player = null;
let syncInterval = null;
let activeSegmentId = null;

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
  syncInterval = setInterval(syncTranscript, 250);
}

function onPlayerStateChange(event) {
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
    if (activeSegmentId) {
      const prev = document.getElementById(activeSegmentId);
      if (prev) prev.classList.remove('segment--active');
    }
    found.classList.add('segment--active');
    activeSegmentId = found.id;

    const toggle = document.getElementById('auto-scroll-toggle');
    if (toggle && toggle.checked) {
      found.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
}

function seekTo(seconds) {
  if (player && typeof player.seekTo === 'function') {
    player.seekTo(seconds, true);
    player.playVideo();
  }
}

function filterTranscript(query) {
  var entries = document.querySelectorAll('.segment');
  var q = query.toLowerCase().trim();
  entries.forEach(function(el) {
    if (!q || el.dataset.text.includes(q)) {
      el.style.display = '';
    } else {
      el.style.display = 'none';
    }
  });
}