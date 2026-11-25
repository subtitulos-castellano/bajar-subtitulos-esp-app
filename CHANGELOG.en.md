# Changes

English version of the release notes, shown by the app when it is in English. Earlier versions are
only in Spanish: see [CHANGELOG.md](CHANGELOG.md).

## 2.0.0

The first version released for **Windows and Linux** at the same time: from now on, every new version is
for both systems, with the same number. What it brings if you come from 1.x:

- **Now available for Linux** (64-bit PCs with a 2022 or newer distribution): `.deb` (Ubuntu, Debian,
  Linux Mint…), `.rpm` (Fedora, AlmaLinux, Rocky Linux, openSUSE…), AppImage (any distribution, nothing to
  install) and `.tar.gz`. It does the same as on Windows: drag videos and folders, Spanish or English,
  OpenSubtitles accounts in the desktop keyring, theme and text size, icon next to the clock, context menu
  in Dolphin, Nemo and Nautilus, and automatic updates that always check the SHA-256 fingerprint.
- [Linux] Uninstalling it also removes its context menu and the shortcuts on the desktop and the
  taskbar; and if you had removed it from the applications menu by hand, it is back there when you
  reinstall it.
- Download files carry the system in their name (`…-windows-instalador.exe`, `…-linux-amd64.deb`…) and,
  on GitHub, a label saying what they are for. Each version also includes `INSTALAR-<version>.txt` and
  `INSTALAR-<version>.md`: how to install and uninstall, with the exact line to paste into the Linux
  terminal.
- Versions before 1.5.1 do not recognise those names: they announce 2.0.0, but it has to be downloaded
  by hand once.

## 1.5.4

- [Linux] When you **uninstall** the app (the `.deb` or the `.rpm`), the shortcuts you gave it on the
  desktop and on the Plasma taskbar, and its context menu, are removed too. And if you had removed it
  from the applications menu by hand, it appears there again when you reinstall it.
- [Linux] With the AppImage and the `.tar.gz`, the same with the uninstall line in
  `INSTALAR-<version>.txt`.

## 1.5.3

- The install and uninstall instructions on the downloads page are now plain text,
  **`INSTALAR-<version>.txt`**, which opens in any editor (Notepad, Kate, gedit…).

## 1.5.2

- The instructions on the downloads page are now called **`INSTALAR-<version>.md`** and also explain
  how to **uninstall**. On Linux, with the line to paste into the terminal, which also removes the
  context menu.

## 1.5.1

- On the GitHub downloads page, each file now says whether it is for **Windows** or **Linux** and which
  distribution, and there is an **`INSTALAR.md`** with the exact line to paste into the terminal to
  install each Linux file (in Spanish and English).
- Automatic updates already recognise the files of upcoming versions even if they carry the system in
  their name (`…-windows-instalador.exe`, `…-linux-amd64.deb`…).

## 1.5.0

- **Now available for Linux**: the same app, with the same version number as the Windows one. There is a
  `.deb` (Ubuntu, Debian, Linux Mint…), an `.rpm` (Fedora, AlmaLinux, Rocky Linux, openSUSE…), an
  AppImage (any distribution, nothing to install) and a `.tar.gz`. How to choose and install, in the
  README.
- [Linux] It does the same as on Windows:
  - drag videos and folders onto the window, in Spanish or English;
  - OpenSubtitles accounts are stored in the desktop keyring (KWallet or GNOME Keyring);
  - light or dark theme, and text size as a percentage (100 % is the system's normal size);
  - an icon next to the clock to keep running when the window is closed. On GNOME it needs the
    *AppIndicator* extension; without it, the option is disabled with an explanation.
- [Linux] **Context menu** with the right mouse button:
  - in Dolphin (KDE) and Nemo (Cinnamon): *Get subtitles here* on folders (only that folder or also
    its subfolders) and *Get subtitles* on videos;
  - in Nautilus (GNOME), inside *Scripts*;
  - with the `.deb` and the `.rpm` it is added when the app opens; with the AppImage, from Settings. If
    you uninstall the app or delete the AppImage, the menu removes itself the first time you use it.
- [Linux] **Updates**: the `.deb` and the `.rpm` are installed by the system package manager, which asks
  for your password; the AppImage is replaced by the new one. The SHA-256 fingerprint published on
  GitHub is always checked first. The `.tar.gz` only notifies.
- [Linux] The AppImage offers to add itself to the applications menu. If you move it to another folder,
  it is fixed when you open it.

## 1.4.0

- [Windows] **Update notices only when there is something for Windows.** This is the first step
  towards the Linux version: both will always share the same version number, and each one will only
  announce the versions that bring changes for its system. If it skips some, it also shows their
  news.
- [Windows] Under the hood, the code has been reorganised for the Linux version. On Windows everything
  works as before.

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
