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

const FOLDER_MIME = "application/vnd.google-apps.folder";

/**
 * List every file inside a Drive folder (recursively), via the Drive API.
 * Returns [{fileId, fileName, mimeType, accessToken}]. Sub-folders are expanded;
 * folders themselves are not returned. Depth-capped to avoid runaway recursion.
 */
async function listFolderFiles(folderId, accessToken, depth = 0) {
  if (depth > 10) return [];
  const out = [];
  let pageToken = "";
  do {
    const params = new URLSearchParams({
      q: `'${folderId}' in parents and trashed=false`,
      fields: "nextPageToken, files(id,name,mimeType)",
      pageSize: "1000",
      supportsAllDrives: "true",
      includeItemsFromAllDrives: "true",
    });
    if (pageToken) params.set("pageToken", pageToken);
    const res = await fetch(
      `https://www.googleapis.com/drive/v3/files?${params.toString()}`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    if (!res.ok) break;
    const data = await res.json();
    for (const f of data.files || []) {
      if (f.mimeType === FOLDER_MIME) {
        out.push(...(await listFolderFiles(f.id, accessToken, depth + 1)));
      } else {
        out.push({ fileId: f.id, fileName: f.name, mimeType: f.mimeType, accessToken });
      }
    }
    pageToken = data.nextPageToken || "";
  } while (pageToken);
  return out;
}

/**
 * Open Google Drive Picker (multi-select enabled).
 * Folders CAN be selected — a picked folder is expanded to all files inside it.
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
              .setSelectFolderEnabled(true),   // allow picking a whole folder
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
              // Expand any picked folder into the files it contains.
              (async () => {
                const out = [];
                for (const f of data.docs) {
                  if (f.mimeType === FOLDER_MIME) {
                    out.push(...(await listFolderFiles(f.id, accessToken)));
                  } else {
                    out.push({
                      fileId: f.id,
                      fileName: f.name,
                      mimeType: f.mimeType,
                      accessToken,
                    });
                  }
                }
                resolve(out);
              })();
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
