const fileInput = document.getElementById("file");
const VOICE_OPTIONS = [
  "Achernar",
  "Achird",
  "Algenib",
  "Algieba",
  "Alnilam",
  "Aoede",
  "Autonoe",
  "Callirrhoe",
  "Charon",
  "Despina",
  "Enceladus",
  "Erinome",
  "Fenrir",
  "Gacrux",
  "Iapetus",
  "Kore",
  "Laomedeia",
  "Leda",
  "Orus",
  "Puck",
  "Pulcherrima",
  "Rasalgethi",
  "Sadachbia",
  "Sadaltager",
  "Schedar",
  "Sulafat",
  "Umbriel",
  "Vindemiatrix",
  "Zephyr",
  "Zubenelgenubi",
];
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

  speakers.forEach((speaker) => {
    const row = document.createElement("div");
    row.className = "mapping-row";

    const label = document.createElement("label");
    label.textContent = `Voice for ${speaker}`;

    const input = document.createElement("select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Auto (no voice override)";
    input.appendChild(empty);
    VOICE_OPTIONS.forEach((voice) => {
      const opt = document.createElement("option");
      opt.value = voice;
      opt.textContent = voice;
      input.appendChild(opt);
    });

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


form.addEventListener("submit", async (event) => {
  event.preventDefault();
  logsEl.textContent = "Starting processing...";
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

  const logs = [];
  const appendLog = (message) => {
    logs.push(message);
    logsEl.textContent = logs.join("\n");
  };

  try {
    const response = await fetch("/process", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const data = await response.json();
      logsEl.textContent = data.detail || "Processing failed.";
      return;
    }

    if (!response.body) {
      logsEl.textContent = "No response stream available.";
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const handlePayload = (payload) => {
      if (!payload || typeof payload !== "object") return;
      if (payload.type === "log") {
        appendLog(payload.message);
        return;
      }
      if (payload.type === "error") {
        logsEl.textContent = payload.message || "Processing failed.";
        downloadsEl.innerHTML = "";
        return;
      }
      if (payload.type === "result") {
        const resultLogs = Array.isArray(payload.logs) ? payload.logs : logs;
        logsEl.textContent = resultLogs.join("\n");
        downloadsEl.innerHTML = "";
        (payload.downloads || []).forEach((url, index) => {
          const link = document.createElement("a");
          link.href = url;
          link.textContent = `Download audio ${index + 1}`;
          link.className = "download-link";
          link.target = "_blank";
          downloadsEl.appendChild(link);
        });
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      lines.forEach((line) => {
        const trimmed = line.trim();
        if (!trimmed) return;
        try {
          const payload = JSON.parse(trimmed);
          handlePayload(payload);
        } catch (error) {
          // Ignore partial/invalid JSON chunks.
        }
      });
    }

    const tail = buffer.trim();
    if (tail) {
      try {
        handlePayload(JSON.parse(tail));
      } catch (error) {
        // Ignore trailing invalid JSON.
      }
    }
  } catch (error) {
    logsEl.textContent = `Error: ${error.message}`;
  }
});