import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VVPAT_DIR = BASE_DIR / "vvpats"


def print_vvpat_slip(voter_id, candidate_id, candidate_name, timestamp=None):
    """Create a VVPAT record for the demo and optionally send it to a thermal printer.

    The default lab mode writes a printer-ready text record to vvpats/. This makes the
    software demonstrable even when the physical printer is not connected. Set
    THERMAL_PRINTER_ENABLED=true only after integrating the actual printer driver.
    """
    timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    VVPAT_DIR.mkdir(exist_ok=True)

    filename = f"VVPAT_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{voter_id}.txt"
    path = VVPAT_DIR / filename
    slip = (
        "=" * 32 + "\n"
        "          VOTELOCK VVPAT\n"
        "=" * 32 + "\n"
        "Vote successfully recorded\n"
        f"Candidate : {candidate_name}\n"
        f"Candidate ID: {candidate_id}\n"
        f"Time      : {timestamp}\n"
        "Status    : VERIFIED\n"
        "=" * 32 + "\n"
        "This slip is a voter-verifiable\n"
        "paper record for the demo system.\n"
        "=" * 32 + "\n"
    )
    path.write_text(slip, encoding="utf-8")

    if os.getenv("THERMAL_PRINTER_ENABLED", "false").lower() == "true":
        # Hardware-specific printing should be connected here for the final device.
        return {
            "success": False,
            "mode": "demo-file",
            "message": f"VVPAT file created at {path.name}. Hardware printer driver is not configured.",
            "file": str(path.relative_to(BASE_DIR)),
        }

    return {
        "success": True,
        "mode": "demo-file",
        "message": f"VVPAT record created: {path.name}",
        "file": str(path.relative_to(BASE_DIR)),
    }
