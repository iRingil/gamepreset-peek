# Plan

What is left to do. Done work is in the commits and the releases; the reasons behind the code are in
`.claude/notes.md`.

## Open

- [ ] Release 1.1.0 (Build run 40178955439, own theme package and mouse-only focus): test the installer and the
  portable zip in Windows Sandbox, then run the Release workflow. While testing, switch the Windows app mode with the
  theme on "auto" and see the app follow: Qt's `colorSchemeChanged` replaced `darkdetect`, checked only with mocks.
