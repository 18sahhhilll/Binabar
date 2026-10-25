# Binabar: Pre-Launch Tasks and Placeholders

This file tracks every placeholder, manual configuration step, and task needed before taking the site live.

---

## 1. Content Placeholders to Replace

The following text files and templates contain bracketed placeholders that must be filled with real details:

1. **About Page (`templates/core/about.html`)**:
   - `[ABOUT TEXT: Describe what Binabar is and why it exists.]`: Write 1 to 2 paragraphs describing the project in scene-appropriate voice.
   - `[ABOUT TEXT: Describe who runs the project. Do not invent a team, founders, or a story.]`: State clearly who maintains the site.

2. **Privacy Policy Page (`templates/core/privacy.html`)**:
   - `[LEGAL ENTITY / OWNER NAME]`: Your legal entity, organisation, or individual operator name.
   - `[LAST UPDATED DATE]`: The current calendar date when launched.
   - `[HOSTING PROVIDER]`: The hosting provider name (e.g. Render, AWS, DigitalOcean).
   - `[CONTACT EMAIL]`: Official email address for data inquiries.

3. **Terms and Conditions Page (`templates/core/terms.html`)**:
   - `[LAST UPDATED DATE]`: The current calendar date when launched.
   - `[RESPONSE TIME, for example 7 days]`: The policy turnaround time for takedown requests.
   - `[JURISDICTION]`: Governing legal jurisdiction (e.g. State of Maharashtra, India; or New Delhi, India).
   - `[CONTACT EMAIL]`: Official email address for rights holders.

---

## 2. Environment and Secret Configuration

Before running in production:

1. **`SECRET_KEY`**: Generate a cryptographically strong 50+ character random key. Never use the development default.
2. **`ADMIN_URL`**: Change from `secret-admin/` to a unique, non-guessable string ending in a slash (for example: `gully-control-8812/`).
3. **`CONTACT_EMAIL`**: Set to your monitored email inbox (e.g. `rights@binabar.com`).
4. **`ALLOWED_HOSTS`**: Configure to your real domain (e.g. `binabar.com,www.binabar.com`).
5. **`CSRF_TRUSTED_ORIGINS`**: Set to `https://binabar.com,https://www.binabar.com`.
6. **Cloudflare R2 Credentials**:
   - `R2_ACCOUNT_ID`
   - `R2_ACCESS_KEY_ID`
   - `R2_SECRET_ACCESS_KEY`
   - `R2_BUCKET_NAME`

---

## 3. Manual Operational Steps

1. **Create Superuser Account**:
   - Run `python manage.py createsuperuser` on your production host shell.
   - Keep exactly one superuser account.

2. **Enable Two-Factor Authentication (TOTP)**:
   - Immediately visit `/account/two_factor/setup/` while logged in.
   - Pair with an authenticator application (Google Authenticator, Bitwarden, etc.).
   - Copy emergency recovery tokens into a secure vault.

3. **Verify Audio Bucket CORS and Lifecycles**:
   - In Cloudflare R2 bucket settings, configure CORS to allow requests from your production domain if necessary.

---

## 4. Song Credits Verification Checklist

Every song added to Binabar must be verified before ticking the `verified` checkbox. Do not mark as verified until confirming:

1. **Artist display name**: Matches official streaming release (Spotify, Apple Music, YouTube Music).
2. **Artists list**: Includes all featured artists explicitly.
3. **Producers**: Verified from album liner notes or official audio metadata. Never guess a producer.
4. **Label**: Verified official publishing or distribution label.
5. **Release year**: Verified original release date (1990 to current year).
6. **Clip duration**: Strictly between 8 and 20 seconds.
7. **Source URL**: Verified HTTPS link to official music video or audio stream.
