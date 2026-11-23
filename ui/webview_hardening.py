"""Lock the WebView2 control to AudioClamp's own page.

pywebview injects the Python bridge (window.pywebview.api) into whatever page the WebView shows.
Left at WebView2 defaults, dropping an .html file on the window or following a link would load a
foreign page that gets full control of the app. After the UI has loaded this:
  - cancels every navigation (top level and frames) away from the page's own origin; user-clicked
    http(s) links open in the default browser instead,
  - refuses files and links dragged in from outside,
  - turns off Ctrl+wheel / Ctrl+plus zoom (the layout is pixel-tuned) and form autofill.
DevTools, the default context menu, browser accelerator keys and downloads are already off,
because pywebview ties them to debug=False.
"""
import webbrowser
from typing import Any, Callable, List, Optional
from urllib.parse import urlsplit

ALWAYS_ALLOWED = ("about:blank",)


def origin_of(uri: str) -> str:
    parts = urlsplit(uri)
    if parts.scheme == "file":
        # Every file:// page counts as its own origin: only the app folder itself is allowed
        path = parts.path.rsplit("/", 1)[0]
        return f"file://{parts.netloc}{path}/".lower()
    return f"{parts.scheme}://{parts.netloc}".lower()


def is_navigation_allowed(uri: str, app_origin: str) -> bool:
    if not uri:
        return False
    if uri in ALWAYS_ALLOWED:
        return True
    return bool(app_origin) and origin_of(uri) == app_origin


def harden_webview(window: Any, log: Callable[[str], None] = print) -> Optional[List[Any]]:
    """Apply the lock-down to a loaded pywebview window (WinForms / EdgeChromium backend).
    Returns the .NET event handlers, which the caller must keep referenced for the window's
    lifetime, or None when the backend is not WebView2."""
    form = getattr(window, "native", None)
    webview_ctl = getattr(getattr(form, "browser", None), "webview", None)
    if form is None or webview_ctl is None:
        return None
    try:
        from System import Action
    except Exception as e:
        log(f"[WebviewHardening] .NET bridge unavailable: {e}")
        return None

    handlers: List[Any] = []

    def apply() -> None:
        core = webview_ctl.CoreWebView2
        if core is None:
            return
        app_origin = origin_of(str(core.Source))

        def on_navigation(sender: Any, args: Any) -> None:
            uri = str(args.Uri)
            if is_navigation_allowed(uri, app_origin):
                return
            args.Cancel = True
            scheme = urlsplit(uri).scheme.lower()
            if scheme in ("http", "https") and bool(getattr(args, "IsUserInitiated", False)):
                try:
                    webbrowser.open(uri)
                except Exception:
                    pass
            log(f"[WebviewHardening] Blocked a {scheme or 'non-URL'} navigation away from the app page")

        core.NavigationStarting += on_navigation
        core.FrameNavigationStarting += on_navigation
        handlers.append(on_navigation)

        try:
            webview_ctl.AllowExternalDrop = False
        except Exception as e:
            log(f"[WebviewHardening] Could not disable external drop: {e}")

        settings = core.Settings
        for name, value in (("IsZoomControlEnabled", False),
                            ("IsPinchZoomEnabled", False),
                            ("IsGeneralAutofillEnabled", False),
                            ("IsPasswordAutosaveEnabled", False)):
            try:
                setattr(settings, name, value)
            except Exception:
                pass

    try:
        if form.InvokeRequired:
            form.Invoke(Action(apply))
        else:
            apply()
    except Exception as e:
        log(f"[WebviewHardening] Lock-down failed: {e}")
        return None
    return handlers
