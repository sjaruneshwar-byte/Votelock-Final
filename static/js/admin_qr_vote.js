let scanner = null;
let scannerStarted = false;
let processingQR = false;
let verified = false;
let photoStream = null;
let photoCaptured = false;
let warmupStream = null;

const $ = (id) => document.getElementById(id);

function message(title, detail = "", type = "neutral") {
  const box = $("verification-message");
  if (!box) return;
  box.className = "verify-message " + type;
  box.innerHTML = `<strong>${title}</strong><span>${detail}</span>`;
}

function status(text, live = false) {
  const box = $("scanner-status");
  if (!box) return;
  box.innerHTML = live ? `<span class="pulse"></span> ${text}` : text;
}

function setStep(number) {
  document.querySelectorAll(".station-progress .step").forEach((el, index) => {
    el.classList.toggle("active", index < number);
    el.classList.toggle("current", index === number - 1);
  });
}

function enableCandidates(enabled) {
  document.querySelectorAll(".candidate-btn").forEach((button) => {
    button.disabled = !enabled;
  });
  const label = document.querySelector(".locked-label");
  if (label) label.textContent = enabled ? "READY TO CAST" : "PHOTO REQUIRED";
}

function showVoter(voter) {
  $("voter-details")?.classList.remove("hidden");
  if ($("voter-id")) $("voter-id").textContent = voter.voter_id || "—";
  if ($("voter-name")) $("voter-name").textContent = voter.name || "—";
  if ($("voter-department")) $("voter-department").textContent = voter.department || "Not specified";
  if ($("voter-status")) {
    $("voter-status").textContent = "ELIGIBLE";
    $("voter-status").className = "status-ready";
  }

  const candidateArea = $("candidate-area");
  if (candidateArea) candidateArea.classList.remove("hidden");

  if (voter.image_path && $("captured-photo")) {
    $("captured-photo").src = "/static/" + voter.image_path;
    $("captured-photo").classList.add("visible");
    $("photo-placeholder")?.classList.add("hidden");
  }
}

/*
 * Camera permissions are requested explicitly before html5-qrcode starts.
 * This is important on Windows/Chrome because enumerateDevices() may return
 * unusable/blank camera information until getUserMedia() has been granted.
 */
async function requestCameraPermission() {
  if (!window.isSecureContext) {
    throw new Error(
      "Camera access requires a secure browser context. Open VoteLock using http://127.0.0.1:5000 or http://localhost:5000."
    );
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error(
      "This browser does not support webcam access. Please use the latest Chrome or Edge."
    );
  }

  try {
    warmupStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: { ideal: "user" }
      },
      audio: false
    });

    // Permission is now granted. Stop only this temporary stream.
    warmupStream.getTracks().forEach((track) => track.stop());
    warmupStream = null;
    return true;
  } catch (error) {
    console.error("Camera permission error:", error);

    let detail = "Allow camera access in the browser address-bar permission settings.";
    if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
      detail = "Camera permission was denied. Click the camera/lock icon near the address bar, allow Camera, then click Start camera.";
    } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      detail = "No webcam was found. Check that the laptop camera is connected and not being used by another application.";
    } else if (error.name === "NotReadableError" || error.name === "TrackStartError") {
      detail = "The webcam is already being used by another application such as Teams, Zoom or Camera. Close it and try again.";
    } else if (error.name === "SecurityError") {
      detail = "The browser blocked camera access. Use Chrome/Edge on localhost and allow camera permission.";
    }

    throw new Error(detail);
  }
}

async function stopScanner() {
  if (scanner && scannerStarted) {
    try {
      await scanner.stop();
    } catch (error) {
      console.warn("Scanner stop:", error);
    }
  }

  if (scanner) {
    try {
      await scanner.clear();
    } catch (error) {
      console.warn("Scanner clear:", error);
    }
  }

  scannerStarted = false;
  scanner = null;
}

function populateCameraSelect(cameras) {
  const select = $("camera-select");
  if (!select) return;

  select.innerHTML = "";

  cameras.forEach((camera, index) => {
    const option = document.createElement("option");
    option.value = camera.id;
    option.textContent = camera.label || `Laptop camera ${index + 1}`;
    select.appendChild(option);
  });

  select.style.display = cameras.length > 1 ? "block" : "none";
}

async function getAvailableCameras() {
  // Permission must be requested first so Chrome exposes camera labels.
  await requestCameraPermission();

  const cameras = await Html5Qrcode.getCameras();

  if (!cameras || cameras.length === 0) {
    throw new Error(
      "No webcam was detected. Check Windows Camera permissions and make sure another app is not using the camera."
    );
  }

  populateCameraSelect(cameras);
  return cameras;
}

function chooseLaptopCamera(cameras) {
  const select = $("camera-select");
  const savedId = localStorage.getItem("votelock_camera_id");

  if (savedId && cameras.some((camera) => camera.id === savedId)) {
    return savedId;
  }

  // Prefer a device whose label looks like an integrated/USB webcam.
  const preferred = cameras.find((camera) =>
    /integrated|built.?in|webcam|usb|camera|hd camera|facetime/i.test(camera.label || "")
  );

  return (preferred || cameras[0]).id;
}

async function startScanner(cameraId) {
  if (scannerStarted) return;

  if (!cameraId) {
    throw new Error("No camera was selected.");
  }

  scanner = new Html5Qrcode("qr-reader");

  try {
    await scanner.start(
      { deviceId: { exact: cameraId } },
      {
        fps: 10,
        qrbox: { width: 250, height: 250 },
        aspectRatio: 1.333334
      },
      onScanSuccess,
      onScanFailure
    );

    scannerStarted = true;
    localStorage.setItem("votelock_camera_id", cameraId);
    status("Camera active. Hold the voter's QR code inside the frame.", true);
    message(
      "Camera ready",
      "Ask the authenticated voter to display their QR code to the laptop webcam.",
      "neutral"
    );
  } catch (error) {
    console.error("Scanner start error:", error);

    try {
      // Fallback for browsers that reject an exact deviceId constraint.
      await scanner.clear();
    } catch (_) {}

    scanner = new Html5Qrcode("qr-reader");

    try {
      await scanner.start(
        { facingMode: "user" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        onScanSuccess,
        onScanFailure
      );

      scannerStarted = true;
      status("Laptop webcam active. Scan the voter's QR.", true);
      return;
    } catch (fallbackError) {
      console.error("Scanner fallback error:", fallbackError);
      scanner = null;
      scannerStarted = false;
      throw new Error(
        "The laptop webcam could not be started. Allow Camera permission in Chrome/Edge, close other camera apps, then click Start camera again."
      );
    }
  }
}

async function initCamera() {
  const startButton = $("start-camera-btn");

  if (typeof Html5Qrcode === "undefined") {
    status("QR scanner library failed to load. Check your internet connection.", false);
    message(
      "Scanner library unavailable",
      "The QR scanner library could not be loaded. Refresh the page or check the internet connection.",
      "error"
    );
    if (startButton) startButton.disabled = true;
    return;
  }

  try {
    status("Requesting laptop camera permission…", true);
    const cameras = await getAvailableCameras();
    const cameraId = chooseLaptopCamera(cameras);

    if ($("camera-select")) {
      $("camera-select").value = cameraId;
    }

    await startScanner(cameraId);

    if (startButton) {
      startButton.textContent = "Restart camera";
      startButton.disabled = false;
    }
  } catch (error) {
    console.error("Camera initialization error:", error);
    status(error.message || "Unable to access the laptop webcam.", false);
    message(
      "Camera access needed",
      error.message || "Allow camera access and click Start camera.",
      "error"
    );
    if (startButton) {
      startButton.textContent = "Start camera";
      startButton.disabled = false;
    }
  }
}

async function restartCamera() {
  await stopScanner();
  processingQR = false;
  verified = false;

  if ($("qr-reader")) $("qr-reader").innerHTML = "";

  initCamera();
}

function onScanSuccess(decodedText) {
  if (processingQR || verified || !decodedText) return;

  processingQR = true;
  status("QR detected. Verifying voter…", true);
  verifyQR(decodedText);
}

function onScanFailure(_) {
  // Normal while no QR code is visible.
}

async function startPhotoCamera() {
  const video = $("photo-video");
  if (!video || !navigator.mediaDevices?.getUserMedia) {
    if ($("photo-status")) {
      $("photo-status").textContent = "Camera capture is not supported by this browser.";
    }
    return;
  }

  try {
    stopPhotoCamera();

    photoStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: { ideal: "user" }
      },
      audio: false
    });

    video.srcObject = photoStream;

    await new Promise((resolve) => {
      if (video.readyState >= 2) {
        resolve();
      } else {
        video.onloadedmetadata = () => resolve();
      }
    });

    await video.play();

    $("capture-photo-btn").disabled = false;
    $("photo-status").textContent = "Camera ready. Position the voter and capture the photo.";
  } catch (error) {
    console.error("Photo camera error:", error);
    $("capture-photo-btn").disabled = true;

    let text = "Unable to access the photo camera. Allow camera permission and try again.";
    if (error.name === "NotReadableError") {
      text = "The webcam is busy. Close Camera, Teams, Zoom or another application using it, then try again.";
    } else if (error.name === "NotAllowedError") {
      text = "Camera permission was denied. Allow camera access in the browser settings.";
    }

    $("photo-status").textContent = text;
  }
}

function stopPhotoCamera() {
  if (photoStream) {
    photoStream.getTracks().forEach((track) => track.stop());
    photoStream = null;
  }

  const video = $("photo-video");
  if (video) video.srcObject = null;
}

async function capturePhoto() {
  if (!verified) {
    $("photo-status").textContent = "Verify the voter QR first.";
    return;
  }

  const video = $("photo-video");
  const canvas = $("photo-canvas");
  const button = $("capture-photo-btn");

  if (!video || !video.videoWidth) {
    $("photo-status").textContent = "Photo camera is not ready yet.";
    return;
  }

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  button.disabled = true;
  $("photo-status").textContent = "Saving verified voter photo…";

  try {
    const response = await fetch("/qr/capture-photo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: canvas.toDataURL("image/jpeg", 0.86)
      })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      throw new Error(data.message || "Photo capture failed.");
    }

    photoCaptured = true;

    $("captured-photo").src = data.image_url;
    $("captured-photo").classList.add("visible");
    $("photo-placeholder")?.classList.add("hidden");

    video.classList.add("captured");

    $("photo-status").textContent =
      "✓ Photo captured and linked to this verified voter.";

    $("capture-photo-btn").textContent = "Retake voter photo";
    $("capture-photo-btn").disabled = false;
    $("capture-photo-btn").onclick = capturePhoto;

    enableCandidates(true);
    setStep(4);

    stopPhotoCamera();
  } catch (error) {
    console.error("Photo capture error:", error);
    $("photo-status").textContent = error.message || "Photo capture failed.";
    button.disabled = false;
  }
}

async function verifyQR(token) {
  try {
    message(
      "Checking voter record…",
      "The QR token is being verified against the election database.",
      "loading"
    );

    const response = await fetch("/qr/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_token: token })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      message(
        "QR verification failed",
        data.message || "The QR code could not be verified.",
        "error"
      );
      processingQR = false;
      status("QR rejected. You can scan another voter.", false);
      return;
    }

    verified = true;
    photoCaptured = false;

    showVoter(data.voter);

    message(
      "Voter verified",
      "The voter is eligible. Capture the polling-station photo before casting the vote.",
      "success"
    );

    status("Voter verified. QR scanner paused.", false);
    setStep(2);

    await stopScanner();

    if ($("start-camera-btn")) {
      $("start-camera-btn").disabled = true;
      $("start-camera-btn").textContent = "QR verified";
    }

    await startPhotoCamera();

    $("capture-photo-btn").onclick = capturePhoto;
    setStep(3);
  } catch (error) {
    console.error("QR verification error:", error);
    message(
      "Connection error",
      "Unable to connect to the VoteLock server.",
      "error"
    );
    status("Server connection failed.", false);
    processingQR = false;
  }
}

async function castVote(candidateId) {
  if (!verified) {
    message(
      "Voter verification required",
      "Scan a valid voter QR before selecting a candidate.",
      "error"
    );
    return;
  }

  if (!photoCaptured) {
    message(
      "Photo capture required",
      "Capture the verified voter's photo before casting the vote.",
      "error"
    );
    return;
  }

  const button = document.querySelector(
    `[data-candidate-id="${CSS.escape(candidateId)}"]`
  );

  const candidateName =
    button?.querySelector("strong")?.textContent || candidateId;

  if (
    !confirm(
      `Record the vote for ${candidateName}?\n\nThis action cannot be undone.`
    )
  ) {
    return;
  }

  const buttons = [...document.querySelectorAll(".candidate-btn")];
  buttons.forEach((b) => (b.disabled = true));

  message(
    "Recording vote…",
    "The vote is being stored and the VVPAT workflow is being triggered.",
    "loading"
  );

  try {
    const response = await fetch("/voting/cast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidateId })
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      message(
        "Vote not recorded",
        data.message || "The vote could not be recorded.",
        "error"
      );
      buttons.forEach((b) => (b.disabled = false));
      return;
    }

    $("candidate-area").classList.add("hidden");
    $("success-box").classList.remove("hidden");

    $("success-text").textContent =
      `${data.voter_name} · ${data.candidate_name}`;

    $("vvpat-text").textContent =
      data.vvpat?.message || "VVPAT record generated.";

    message(
      "Vote recorded successfully",
      "The voter has been marked as voted and the transaction is complete.",
      "success"
    );

    status("Transaction complete. Ready for the next voter.", false);
    setStep(5);

    verified = false;
    photoCaptured = false;
    stopPhotoCamera();
  } catch (error) {
    console.error(error);
    message(
      "Server connection failed",
      "The vote could not be completed.",
      "error"
    );
    buttons.forEach((b) => (b.disabled = false));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  enableCandidates(false);

  const capture = $("capture-photo-btn");
  if (capture) capture.onclick = capturePhoto;

  document.querySelectorAll(".candidate-btn").forEach((button) => {
    button.addEventListener("click", () =>
      castVote(button.dataset.candidateId)
    );
  });

  const startButton = $("start-camera-btn");
  if (startButton) {
    startButton.addEventListener("click", restartCamera);
  }

  const cameraSelect = $("camera-select");
  if (cameraSelect) {
    cameraSelect.addEventListener("change", async () => {
      if (verified) return;

      try {
        await stopScanner();

        const selectedId = cameraSelect.value;
        localStorage.setItem("votelock_camera_id", selectedId);

        await startScanner(selectedId);
      } catch (error) {
        console.error(error);
        status(error.message || "Unable to switch camera.", false);
        message(
          "Camera switch failed",
          "The selected camera could not be started.",
          "error"
        );
      }
    });
  }

  initCamera();
});

window.addEventListener("beforeunload", () => {
  stopScanner();
  stopPhotoCamera();

  if (warmupStream) {
    warmupStream.getTracks().forEach((track) => track.stop());
    warmupStream = null;
  }
});
