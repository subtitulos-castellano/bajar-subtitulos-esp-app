# Changes

English version of the release notes, shown by the app when it is in English. Earlier versions are
only in Spanish: see [CHANGELOG.md](CHANGELOG.md).

## 1.3.0

- **opensubtitles.com**, as a last resort: with an account, it is asked for subtitles only if the other
  providers have not found Spanish from Spain (or, at the end, English), because its accounts only allow
  a few downloads a day.
  - It stops as soon as it finds valid Spanish from Spain, to use as little quota as possible.
  - *Details* shows how many downloads are left today. If the quota runs out (or the account is not
    accepted), it says so and the search goes on with the other providers.
- *Settings › OpenSubtitles accounts*: the opensubtitles.org and opensubtitles.com accounts, each with its
  username, password, *Save* and *Test connection*. *Use the skill's account* imports each one from its
  `credenciales.json` (`"opensubtitlescom"` for the .com one).

## 1.2.1

- **What's new in an update**: if it is long, it can be read in full with a scroll bar (or the mouse
  wheel). It no longer stretches the notice or leaves the rest of the window without room.

## 1.2.0

- **The app, now also in English**:
  - the installer asks for the language the first time (it suggests the Windows one); updates keep
    the previous one;
  - in *Settings › Idioma · Language* it can be changed at any time (in the portable version, it is
    the only way). The app closes and opens again by itself in the chosen language;
  - everything changes: the interface, the notifications, the update notes, the *Details* log and the
    File Explorer context menu.
- The command line and the skill stay in Spanish.
