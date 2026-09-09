"use strict";

const selectedResultStorageKey = "yamahaLocalSelectedResultId";
const select = document.querySelector("#result");
const frame = document.querySelector("#frame");
const input = document.querySelector("#midi");
const fileLabel = document.querySelector(".file-picker span");
const downloadButton = document.querySelector("#download");

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.message || `Request failed: ${response.status}`);
  }
  return body;
}

async function loadResults(preferredId) {
  const data = await api("/api/midi");
  select.replaceChildren();
  for (const item of data.items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.filename;
    select.appendChild(option);
  }
  if (!data.items.length) {
    localStorage.removeItem(selectedResultStorageKey);
    downloadButton.disabled = true;
    frame.removeAttribute("src");
    frame.srcdoc = '<div class="empty">No MIDI files yet.</div>';
    return;
  }
  const remembered =
    preferredId || localStorage.getItem(selectedResultStorageKey);
  if (remembered && data.items.some((item) => item.id === remembered)) {
    select.value = remembered;
  }
  openSelected();
}

function openSelected() {
  const id = select.value;
  if (!id) return;
  localStorage.setItem(selectedResultStorageKey, id);
  downloadButton.disabled = true;
  frame.removeAttribute("srcdoc");
  frame.src = `/share/${encodeURIComponent(id)}/share.html`;
}

function downloadMidi() {
  try {
    const doc = frame.contentDocument;
    const manifestNode = doc?.querySelector(".msr-manifest");
    if (!manifestNode) return;
    const manifest = JSON.parse(manifestNode.textContent);
    const bpm = doc.querySelector('input[aria-label="BPM"]')?.value || manifest.bpm;
    const firstBeat =
      doc.querySelector('input[aria-label="第一拍延遲秒數"]')?.value || 0;
    const params = new URLSearchParams({
      midi_url: manifest.downloads.midi,
      bpm: String(bpm),
      first_beat: String(firstBeat),
    });
    const link = document.createElement("a");
    link.href = `/api/midi-fix?${params.toString()}`;
    link.download = "";
    link.click();
  } catch (error) {
    console.error("MIDI download failed:", error);
  }
}

async function importMidi(file) {
  const form = new FormData();
  form.append("file", file);
  input.disabled = true;
  fileLabel.textContent = "Importing...";
  try {
    const item = await api("/api/midi", { method: "POST", body: form });
    await loadResults(item.id);
  } catch (error) {
    console.error("MIDI import failed:", error);
  } finally {
    input.value = "";
    input.disabled = false;
    fileLabel.textContent = "Import MIDI";
  }
}

input.addEventListener("change", () => {
  const file = input.files[0];
  if (file) void importMidi(file);
});

frame.addEventListener("load", () => {
  downloadButton.disabled = !frame.contentDocument?.querySelector(".msr-manifest");
});

downloadButton.addEventListener("click", downloadMidi);
select.addEventListener("change", openSelected);

document.querySelector("#delete").addEventListener("click", async () => {
  const id = select.value;
  const title = select.options[select.selectedIndex]?.textContent || id;
  if (!id || !window.confirm(`Delete this MIDI file?\n\n${title}`)) return;
  try {
    await api(`/api/midi/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    await loadResults();
  } catch (error) {
    console.error("MIDI delete failed:", error);
  }
});

loadResults().catch((error) => {
  console.error("MIDI library load failed:", error);
});
