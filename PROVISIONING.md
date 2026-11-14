# Provisioning model — vanilla image + script (owner decision 2026-11-12)

The image is **plain MikroTik CHR** (official download at build time,
nothing baked in). Branding and the default login are applied AFTER a
deployment boots, by **`provision.py`** in this folder:

> **Worked example:** the user, password, and branding referenced in this
> document (`ramez` / `ramez`, the RMZ package) are this repo's example
> implementation of the model. Anyone adopting the model substitutes
> their own admin credentials and generates their own `.dpk` — the
> scripts are a template to adapt, not a fixed configuration to deploy.

1. Waits for the RouterOS API, logs in as `admin` (blank password —
   proof it's a pristine image).
2. Creates the branded admin user (**ramez / ramez**, group full) and
   verifies the new login on a second connection.
3. Serves the branding `.dpk` from a one-shot HTTP server and has the
   router `/tool fetch` it; verifies the file size on the router.
4. Reboots — RouterOS installs the package: **ASCII terminal logo**,
   identity/Company URL, and the **defconfig** from `defconfig.rsc`
   (which re-asserts ramez and survives future
   `/system reset-configuration` runs).
5. Logs back in as ramez, lists packages, and only THEN disables the
   built-in `admin` account.

## The .dpk still comes from Branding Maker (Ramez, ~5 min, any browser)
mikrotik.com → log in → **Other → Branding Maker** → ASCII Logo (≤8
lines), Company URL, router name, Default configuration = upload
`defconfig.rsc` from this folder → generate → download `.dpk`.
(The logo/defconfig live in the package — no script can set the ASCII
logo directly; delivering the package IS the script's branding job.)

## Notes
- A fresh deploy from the vanilla image always needs one provision run;
  it can later be wired as a Dokploy post-deploy command. After a mere
  container restart nothing is needed (state lives on the volume disk).
- `--serve-ip` must be an address the GUEST can reach: with the
  entrypoint bridge plan that's `172.24.0.1`; verify against the real
  topology Friday (script's checklist is in its docstring).
- Public-template question (still open for Friday): the template can ship
  the vanilla image + this script with placeholder credentials, while
  Ramez's own deploys run it with ramez/ramez — the script model makes
  that split trivial, no second image needed.
