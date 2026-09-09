"use strict";

const selectedResultStorageKey = "yamahaLocalSelectedResultId";
const select = document.querySelector("#result");
const frame = document.querySelector("#frame");
const input = document.querySelector("#midi");
const fileLabel = document.querySelector(".file-picker span");
const message = document.querySelector("#message");

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

input.addEventListener("change", () => {
  const file = input.files[0];
  fileLabel.textContent = file ? file.name : "Select a MIDI file";
  message.textContent = file ? `Selected: ${file.name}` : "";
});

document.querySelector("#open").addEventListener("click", openSelected);
select.addEventListener("change", openSelected);

document.querySelector("#upload").addEventListener("click", async () => {
  const file = input.files[0];
  if (!file) {
    message.textContent = "Select a MIDI file first.";
    return;
  }
  const form = new FormData();
  form.append("file", file);
  message.textContent = `Uploading: ${file.name}`;
  try {
    const item = await api("/api/midi", { method: "POST", body: form });
    input.value = "";
    fileLabel.textContent = "Select a MIDI file";
    message.textContent = `Uploaded: ${item.filename}`;
    await loadResults(item.id);
  } catch (error) {
    message.textContent = error.message;
  }
});

document.querySelector("#delete").addEventListener("click", async () => {
  const id = select.value;
  const title = select.options[select.selectedIndex]?.textContent || id;
  if (!id || !window.confirm(`Delete this MIDI file?\n\n${title}`)) return;
  try {
    const result = await api(`/api/midi/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    message.textContent = `Deleted: ${result.deleted}`;
    await loadResults();
  } catch (error) {
    message.textContent = error.message;
  }
});

loadResults().catch((error) => {
  message.textContent = error.message;
});
