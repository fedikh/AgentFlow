/**
 * Google Drive Picker Hook
 * Opens Google Drive file picker, returns selected file info.
 *
 * Requires in frontend/.env:
 *   VITE_GOOGLE_CLIENT_ID
 *   VITE_GOOGLE_API_KEY
 *   VITE_GOOGLE_APP_ID
 */
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY;
const APP_ID = import.meta.env.VITE_GOOGLE_APP_ID;
const SCOPES = "https://www.googleapis.com/auth/drive.readonly";

let gapiLoaded = false;
let gisLoaded = false;
let tokenClient = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

async function ensureLoaded() {
  if (!gapiLoaded) {
    await loadScript("https://apis.google.com/js/api.js");
    await new Promise((resolve) => window.gapi.load("picker", resolve));
    gapiLoaded = true;
  }
  if (!gisLoaded) {
    await loadScript("https://accounts.google.com/gsi/client");
    gisLoaded = true;
  }
}

/**
 * Open Google Drive Picker (multi-select enabled).
 * Returns: array of {fileId, fileName, mimeType, accessToken} or null if cancelled.
 */
export async function openGooglePicker() {
  await ensureLoaded();

  return new Promise((resolve) => {
    tokenClient = window.google.accounts.oauth2.initTokenClient({
      client_id: CLIENT_ID,
      scope: SCOPES,
      callback: (response) => {
        if (response.error) {
          console.error("Google auth error:", response);
          resolve(null);
          return;
        }

        const accessToken = response.access_token;

        const picker = new window.google.picker.PickerBuilder()
          .setAppId(APP_ID)
          .setOAuthToken(accessToken)
          .setDeveloperKey(API_KEY)
          .addView(
            new window.google.picker.DocsView()
              .setIncludeFolders(true)
              .setSelectFolderEnabled(false),
          )
          .addView(
            new window.google.picker.DocsView(
              window.google.picker.ViewId.SPREADSHEETS,
            ),
          )
          .addView(
            new window.google.picker.DocsView(
              window.google.picker.ViewId.PRESENTATIONS,
            ),
          )
          .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
          .setCallback((data) => {
            if (data.action === window.google.picker.Action.PICKED) {
              const files = data.docs.map((f) => ({
                fileId: f.id,
                fileName: f.name,
                mimeType: f.mimeType,
                accessToken: accessToken,
              }));
              resolve(files);
            } else if (data.action === window.google.picker.Action.CANCEL) {
              resolve(null);
            }
          })
          .build();

        picker.setVisible(true);
      },
    });

    tokenClient.requestAccessToken();
  });
}
