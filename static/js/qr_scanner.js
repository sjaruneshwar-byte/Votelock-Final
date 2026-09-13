let scanner = null;
let scannerStarted = false;
let processingQR = false;

// ============================================================
// SHOW MESSAGE
// ============================================================

function showMessage(message, type) {
  const messageBox = document.getElementById("verification-message");

  if (!messageBox) {
    return;
  }

  messageBox.textContent = message;

  messageBox.className = "verification-message " + type;
}

// ============================================================
// SHOW VOTER DETAILS
// ============================================================

function showVoter(voter) {
  const voterDetails = document.getElementById("voter-details");

  if (!voterDetails) {
    return;
  }

  voterDetails.style.display = "block";

  document.getElementById("voter-id").textContent = voter.voter_id;

  document.getElementById("voter-name").textContent = voter.name;

  document.getElementById("voter-email").textContent = voter.email || "-";

  document.getElementById("voter-department").textContent =
    voter.department || "-";

  const statusElement = document.getElementById("voter-status");

  if (voter.has_voted === 1) {
    statusElement.textContent = "Already Voted";

    statusElement.className = "status-voted";
  } else {
    statusElement.textContent = "Not Voted";

    statusElement.className = "status-pending";
  }
}

// ============================================================
// VERIFY QR WITH FLASK
// ============================================================

async function verifyQR(qrToken) {
  try {
    showMessage("Verifying QR code...", "loading");

    const response = await fetch("/qr/verify", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        qr_token: qrToken,
      }),
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      showMessage(data.message || "Invalid QR code.", "error");

      processingQR = false;

      updateScannerStatus("QR rejected. You can scan another QR code.");

      return;
    }

    showMessage("✓ Voter verified successfully.", "success");

    showVoter(data.voter);

    updateScannerStatus("✓ Voter verified. Scan another QR code when ready.");

    processingQR = false;
  } catch (error) {
    console.error("QR verification error:", error);

    showMessage("Unable to connect to the server.", "error");

    updateScannerStatus("Server connection failed. Try again.");

    processingQR = false;
  }
}

// ============================================================
// UPDATE SCANNER STATUS
// ============================================================

function updateScannerStatus(message) {
  const status = document.getElementById("scanner-status");

  if (status) {
    status.textContent = message;
  }
}

// ============================================================
// QR SCAN SUCCESS
// ============================================================

function onScanSuccess(decodedText) {
  if (processingQR) {
    return;
  }

  if (!decodedText) {
    return;
  }

  processingQR = true;

  updateScannerStatus("✓ QR code detected. Verifying...");

  verifyQR(decodedText);
}

// ============================================================
// QR SCAN FAILURE
// ============================================================

function onScanFailure(error) {
  // QR not detected yet.
  // Do not display continuous errors.
}

// ============================================================
// START CAMERA
// ============================================================

async function startScanner(cameraId) {
  if (scannerStarted) {
    return;
  }

  try {
    scanner = new Html5Qrcode("qr-reader");

    const cameraConfig = cameraId
      ? cameraId
      : {
          facingMode: "environment",
        };

    await scanner.start(
      cameraConfig,

      {
        fps: 10,

        qrbox: {
          width: 250,
          height: 250,
        },
      },

      onScanSuccess,

      onScanFailure,
    );

    scannerStarted = true;

    updateScannerStatus("Camera active. Scan the QR code.");
  } catch (error) {
    console.error("Camera start error:", error);

    updateScannerStatus("Unable to access camera. Check camera permission.");
  }
}

// ============================================================
// GET AVAILABLE CAMERAS
// ============================================================

async function initializeCamera() {
  try {
    const cameras = await Html5Qrcode.getCameras();

    if (!cameras || cameras.length === 0) {
      updateScannerStatus("No camera detected. Connect the USB webcam.");

      return;
    }

    const cameraSelect = document.getElementById("camera-select");

    // ----------------------------------------------------
    // ADD AVAILABLE CAMERAS TO DROPDOWN
    // ----------------------------------------------------

    if (cameraSelect) {
      cameraSelect.innerHTML = "";

      cameras.forEach(function (camera, index) {
        const option = document.createElement("option");

        option.value = camera.id;

        option.textContent = camera.label || "Camera " + (index + 1);

        cameraSelect.appendChild(option);
      });

      cameraSelect.style.display = "block";

      cameraSelect.addEventListener("change", async function () {
        await switchCamera(cameraSelect.value);
      });
    }

    // ----------------------------------------------------
    // SELECT CAMERA
    // ----------------------------------------------------

    let selectedCamera = cameras[0];

    // Prefer USB/external camera when
    // browser provides a useful label.

    const externalCamera = cameras.find(function (camera) {
      const label = (camera.label || "").toLowerCase();

      return (
        label.includes("usb") ||
        label.includes("external") ||
        label.includes("webcam")
      );
    });

    if (externalCamera) {
      selectedCamera = externalCamera;
    }

    await startScanner(selectedCamera.id);
  } catch (error) {
    console.error("Camera initialization error:", error);

    updateScannerStatus("Camera permission denied or camera unavailable.");
  }
}

// ============================================================
// SWITCH CAMERA
// ============================================================

async function switchCamera(cameraId) {
  if (!cameraId) {
    return;
  }

  try {
    if (scannerStarted && scanner) {
      await scanner.stop();

      await scanner.clear();

      scannerStarted = false;
    }

    processingQR = false;

    const voterDetails = document.getElementById("voter-details");

    if (voterDetails) {
      voterDetails.style.display = "none";
    }

    showMessage("Scan a QR code to verify the voter.", "");

    updateScannerStatus("Starting selected camera...");

    await startScanner(cameraId);
  } catch (error) {
    console.error("Camera switch error:", error);

    updateScannerStatus("Unable to switch camera.");
  }
}

// ============================================================
// PAGE LOAD
// ============================================================

document.addEventListener("DOMContentLoaded", function () {
  if (typeof Html5Qrcode === "undefined") {
    updateScannerStatus("QR scanner library failed to load.");

    return;
  }

  initializeCamera();
});
