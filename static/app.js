"use strict";

const selectedResultStorageKey = "yamahaLocalSelectedResultId";
const select = document.querySelector("#result");
const frame = document.querySelector("#frame");
const input = document.querySelector("#midi");
const fileLabel = document.querySelector(".file-picker span");

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
  frame.removeAttribute("srcdoc");
  frame.src = `/share/${encodeURIComponent(id)}/share.html`;
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

document.querySelector("#open").addEventListener("click", openSelected);
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
