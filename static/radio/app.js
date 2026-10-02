const player = document.getElementById("player");
const nowPlaying = document.getElementById("now-playing");
const nowTrack = document.getElementById("now-track");
const playButtons = document.querySelectorAll(".play-btn");
let activeStationId = null;
let trackPollTimer = null;

function stopTrackPolling() {
  if (trackPollTimer) {
    clearInterval(trackPollTimer);
    trackPollTimer = null;
  }
}

async function updateCurrentTrack() {
  if (!activeStationId || !nowTrack) {
    return;
  }
  try {
    const response = await fetch(`/current-track/${activeStationId}/`);
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    nowTrack.textContent = `Track: ${data.track || "-"}`;
    const nowBitrate = document.getElementById("now-bitrate");
    if (nowBitrate) {
      nowBitrate.textContent = data.bitrate ? `${data.bitrate} kbps` : "";
    }
  } catch {
    nowTrack.textContent = "Track: -";
  }
}

playButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const streamUrl = button.dataset.url;
    const stationName = button.dataset.name || "Unknown station";
    const stationId = button.dataset.stationId;

    if (!streamUrl) {
      return;
    }

    activeStationId = stationId || null;
    stopTrackPolling();
    player.src = streamUrl;
    player.play().catch(() => {
      nowPlaying.textContent = "Unable to play this stream.";
    });
    nowPlaying.textContent = `Now playing: ${stationName}`;
    if (nowTrack) {
      nowTrack.textContent = "Track: loading...";
    }
    const nowBitrate = document.getElementById("now-bitrate");
    if (nowBitrate) {
      nowBitrate.textContent = "";
    }
    updateCurrentTrack();
    trackPollTimer = setInterval(updateCurrentTrack, 20000);
  });
});

player.addEventListener("error", () => {
  nowPlaying.textContent = "Stream error. Please try another station.";
  if (nowTrack) {
    nowTrack.textContent = "Track: -";
  }
  const nowBitrate = document.getElementById("now-bitrate");
  if (nowBitrate) {
    nowBitrate.textContent = "";
  }
  stopTrackPolling();
});

player.addEventListener("pause", () => {
  stopTrackPolling();
});
