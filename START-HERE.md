# Job Hunter: no coding, no VS Code

You do this ONCE (about 15 minutes, all in the browser). After that the jobs update
themselves every 6 hours and you just open a link, on your Mac or your phone.

## Step 1: Make a GitHub account and a repository
1. Go to https://github.com and sign up (free).
2. Click **+ → New repository**. Name it `job-hunter`, choose **Public**, click **Create repository**.

## Step 2: Upload the files
1. Unzip this package on your computer.
2. In your new repository click **uploading an existing file**.
3. Drag in everything that is INSIDE the unzipped `job-hunter` folder
   (the `docs` folder, `hunter.py`, `config.yaml`, `companies.yaml`, `requirements.txt`, `README.md`).
4. Click **Commit changes**.

## Step 3: Add the schedule file
1. In the repository click **Add file → Create new file**.
2. In the name box type exactly: `.github/workflows/hunt.yml`
   (typing the slashes creates the folders).
3. Open `github-workflow-hunt.yml` from this package, copy everything, paste it into the big box.
4. Click **Commit changes**.

## Step 4: Allow it to save results
Repository **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.

## Step 5: Turn on the website
Repository **Settings → Pages → Source: Deploy from a branch → Branch: main, folder: /docs → Save**.

## Step 6: Run it the first time
Click **Actions → Job Hunter → Run workflow**. Wait 1 to 2 minutes.

## Step 7: Open your app
Your link is `https://YOUR-GITHUB-USERNAME.github.io/job-hunter/`
- **Mac / Windows:** open it in Chrome or Edge, click the install icon in the address bar (Install Job Hunter). It becomes a normal desktop app.
- **iPhone:** open in Safari, Share, Add to Home Screen.
- **Android:** open in Chrome, menu, Install app.

## Optional
- **Adzuna (more jobs):** get a free key at https://developer.adzuna.com, then repository
  Settings → Secrets and variables → Actions → add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- **Phone alerts:** see section 3 of README.md (Telegram).
- **Change what it searches:** edit `config.yaml` right on GitHub (pencil icon).
- **Update right now:** use the "Update jobs now" link at the bottom of the app.

## Privacy note
A public repository means anyone could see your search settings (keywords, Kassel). It holds no
passwords. Your Save / Applied / Hide marks stay only in your own browser.
