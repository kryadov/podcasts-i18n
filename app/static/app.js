const fileInput = document.getElementById("file");
const voicesInput = document.getElementById("voices");
const mappingContainer = document.getElementById("speaker-mapping");
const logsEl = document.getElementById("logs");
const downloadsEl = document.getElementById("downloads");
const form = document.getElementById("upload-form");

function parseSpeakers(text) {
  const lines = text.split(/\r?\n/);
  const speakers = [];
  const seen = new Set();
  const re = /^(?<speaker>.+?)\s+\d{2}:\d{2}:\d{2}\s*$/;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    const match = line.match(re);
    if (match && match.groups && match.groups.speaker) {
      const speaker = match.groups.speaker.trim();
      if (!seen.has(speaker)) {
        speakers.push(speaker);
        seen.add(speaker);
      }
    }
  }
  return speakers;
}

function renderSpeakerMapping(speakers) {
  mappingContainer.innerHTML = "";
  if (speakers.length === 0) {
    mappingContainer.innerHTML = "<p class=\"muted\">No speakers detected yet.</p>";
    return;
  }

  const voices = voicesInput.value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

  speakers.forEach((speaker) => {
    const row = document.createElement("div");
    row.className = "mapping-row";

    const label = document.createElement("label");
    label.textContent = `Voice for ${speaker}`;

    let input;
    if (voices.length > 0) {
      input = document.createElement("select");
      voices.forEach((voice) => {
        const opt = document.createElement("option");
        opt.value = voice;
        opt.textContent = voice;
        input.appendChild(opt);
      });
    } else {
      input = document.createElement("input");
      input.type = "text";
      input.placeholder = "Enter voice name";
    }

    input.dataset.speaker = speaker;
    row.appendChild(label);
    row.appendChild(input);
    mappingContainer.appendChild(row);
  });
}

fileInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const speakers = parseSpeakers(text);
    renderSpeakerMapping(speakers);
  };
  reader.readAsText(file, "UTF-8");
});

voicesInput.addEventListener("input", () => {
  const speakers = Array.from(mappingContainer.querySelectorAll("[data-speaker]")).map(
    (input) => input.dataset.speaker
  );
  renderSpeakerMapping(speakers);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  logsEl.textContent = "Processing...";
  downloadsEl.innerHTML = "";

  const file = fileInput.files[0];
  if (!file) {
    logsEl.textContent = "Please select a file.";
    return;
  }

  const voiceMap = {};
  const inputs = mappingContainer.querySelectorAll("[data-speaker]");
  inputs.forEach((input) => {
    const speaker = input.dataset.speaker;
    voiceMap[speaker] = input.value || "";
  });

  const formData = new FormData(form);
  formData.append("voice_map_json", JSON.stringify(voiceMap));

  try {
    const response = await fetch("/process", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      logsEl.textContent = data.detail || "Processing failed.";
      return;
    }

    logsEl.textContent = data.logs.join("\n");
    downloadsEl.innerHTML = "";
    data.downloads.forEach((url, index) => {
      const link = document.createElement("a");
      link.href = url;
      link.textContent = `Download audio ${index + 1}`;
      link.className = "download-link";
      link.target = "_blank";
      downloadsEl.appendChild(link);
    });
  } catch (error) {
    logsEl.textContent = `Error: ${error.message}`;
  }
});