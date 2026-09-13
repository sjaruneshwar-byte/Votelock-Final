# VoteLock — Smart Electronic Voting System

VoteLock is a smart electronic voting prototype combining a web-based election control system with QR voter authentication, administrator-controlled polling verification, voter photo capture, electronic vote recording, VVPAT and thermal printing.

## Review 1 voting workflow

1. Administrator registers and verifies the admin account through email OTP.
2. Administrator manages voters and candidates from the existing portal.
3. Voter signs in using their assigned credentials.
4. The voter portal displays the voter's secure QR code only.
5. The administrator/polling station scans the QR using the station camera.
6. The system verifies the voter and checks that they have not already voted.
7. The administrator captures a polling-station photo of the verified voter.
8. Candidate selection becomes available only after verification and photo capture.
9. The administrator confirms the selected candidate.
10. The vote is recorded and the voter is marked as voted.
11. The VVPAT/thermal-printer workflow is triggered.

## Existing features retained

- Admin registration
- Email OTP verification
- Admin login/logout
- Admin dashboard
- Voter management
- Add/edit/delete voters
- Temporary voter credentials
- Voter QR generation/display
- Candidate management
- Candidate add/edit/delete
- Audit logging
- Election turnout statistics
- VVPAT/thermal-printer integration
- SQLite persistence

## Technology

- Python
- Flask
- SQLite
- HTML/CSS/JavaScript
- html5-qrcode
- QRCode.js
- Browser camera APIs
- Thermal printer/VVPAT integration

## Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure the SMTP settings.

```bash
python app.py
```

Open:

- Admin: `http://127.0.0.1:5000/login`
- Voter: `http://127.0.0.1:5000/voter/login`
- Admin Verify & Vote: `http://127.0.0.1:5000/qr/scanner`

Camera access should be allowed in the browser. The photo capture feature uses the administrator/polling-station camera after QR verification.

## Security note

Do not commit `.env`, voter database files, captured voter photos, or other credentials to GitHub. The included `.gitignore` excludes these sensitive/local files.
