# Black-and-red app icon

The authoritative source is `app-icon.svg`: a pure red horizontal rounded rectangle with one centered white triangle pointing down. The background is transparent. The two-shape geometry keeps the modified YouTube-style mark crisp at small sizes.

- `app-icon.svg`: editable vector source.
- `app-icon.png`: 1024-pixel native WPF rendering, used by the window, title bar, and sidebar.
- `app-icon.ico`: the same mark at 16, 24, 32, 48, 64, 128, and 256 pixels, embedded in the Windows EXE.

Regenerate from the project folder in CMD:

```cmd
powershell -STA -NoProfile -ExecutionPolicy Bypass -File ".\installer\render-icon.ps1" -Python ".\.venv\Scripts\python.exe"
```

The final icon is drawn from the SVG and rendered with WPF; Pillow is used only for Windows ICO format packaging. Image-generation concepts were explored, but are not used in this final asset.
