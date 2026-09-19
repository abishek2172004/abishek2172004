# Setup

This only works if the repo is named **exactly** your GitHub username — that's
the one special case where GitHub shows a repo's README on your profile page
instead of the repo page.

1. **Create the repo.**
   On GitHub, click "New repository" and name it exactly `abishek2172004`
   (must match your username, case included). Make it **public**. Don't
   initialize it with a README — you're pushing one.

2. **Push these files.**
   ```bash
   cd profile-repo   # this folder
   git init
   git add .
   git commit -m "profile: initial setup"
   git branch -M main
   git remote add origin https://github.com/abishek2172004/abishek2172004.git
   git push -u origin main
   ```

3. **Let the Action write to the repo.**
   Go to the new repo's **Settings → Actions → General → Workflow
   permissions**, and switch it to **"Read and write permissions"**. Without
   this the daily job can generate the SVGs but can't commit them back.

4. **Generate the stats once, manually.**
   Go to the **Actions** tab → "refresh profile stats" (in the sidebar) →
   **Run workflow**. This does the same thing the daily cron does — fetches
   your contribution data and commits `stats.svg`, `streak.svg`, `langs.svg`,
   and `year.svg`. After it finishes (about 10–20 seconds), refresh your
   profile page and the graphics should appear.

5. **Fill in the rest of the README.**
   - Uncomment / edit the LinkedIn, portfolio, and email links at the top.
   - Add more of your own repos to the Projects section as they're ready —
     just follow the same `**[name](link)** — description` format.
   - Everything else (About, Stack) is already filled in from what you'd
     told me; edit freely.

## If the Action fails with a permissions error

The default `GITHUB_TOKEN` is usually enough to read public contribution
data, but if step 3 above didn't fix a `403`/`permission` error:

1. Create a classic Personal Access Token with the `public_repo` and
   `read:user` scopes (**Settings → Developer settings → Personal access
   tokens**).
2. Add it as a repository secret named `GH_PAT` (**Settings → Secrets and
   variables → Actions → New repository secret**).
3. In `.github/workflows/refresh-stats.yml`, change
   `GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}` to
   `GITHUB_TOKEN: ${{ secrets.GH_PAT }}`.

## Extending it

The reference repo you found also includes a self-typing ASCII-art portrait
generated from a photo (`scripts/make_portrait.py` in their repo), using
background removal + a character ramp. It's a nice touch but needs extra
dependencies (`pillow`, `numpy`, `opencv-python`, `rembg`) and a good source
photo, so I left it out of this first pass — happy to build you a version of
it once you've got a photo you like and want to add it.
