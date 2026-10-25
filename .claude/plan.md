# Plan

What is left to do. Done work is in the commits and the releases; the reasons behind the code are in
`.claude/notes.md`.

## Open

- [ ] Own theme package `src/app/ui/flat_theme` (replaced the vendored PyQtDarkTheme; done except these checks):
  - Check by eye in the running app: light, dark, every widget kind (lists, tabs, slider, menus, popups, scroll bars).
  - "auto": switch the Windows app mode while the app runs in auto and see it follow (Qt's `colorSchemeChanged`
    replaced `darkdetect`, verified only with mocks).
  - Run the Build workflow and check the theme's files (`style.qss`, `icons`, `LICENSE.txt`) are in the build.
- [ ] Code signing with SignPath Foundation: the application was submitted on 2026-10-25. Once approved, the Build
  workflow sends `GamePresetPeek.exe` (before packing) and the installer to SignPath through
  `signpath/github-action-submit-signing-request`; the organization id, project slug and signing policy slug come
  with the approval, the API token goes into the repository secrets. Keep the SmartScreen hint in the release notes
  until signed builds have gained reputation.
