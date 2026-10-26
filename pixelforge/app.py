"""PixelForge: screenshot-to-code playground (Streamlit entry point).

Run with:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from pixelforge import __version__
from pixelforge.components.editor import render_code_tab
from pixelforge.components.preview import render_preview
from pixelforge.components.uploader import render_uploader
from pixelforge.config import Settings, load_settings
from pixelforge.schemas import Fidelity, Framework, GenerationOptions, Viewport
from pixelforge.services.ai_generator import generate_code
from pixelforge.services.exporter import build_zip, slugify
from pixelforge.state import SOURCE_AI, SOURCE_DEMO, Workspace, get_workspace
from pixelforge.utils.errors import ConfigError, ExportError, PixelForgeError
from pixelforge.utils.logging_config import get_logger, setup_logging

st.set_page_config(page_title="PixelForge · Screenshot to code", page_icon="🛠️", layout="wide", initial_sidebar_state="expanded")

LOGO_SVG = """<svg width="38" height="38" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
<defs><linearGradient id="pf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7c9cff"/><stop offset="1" stop-color="#b57cff"/></linearGradient></defs>
<rect width="38" height="38" rx="9" fill="url(#pf)"/>
<g fill="#0b0e14"><rect x="9" y="9" width="8" height="8" rx="1.5"/><rect x="21" y="9" width="8" height="8" rx="1.5" opacity=".55"/>
<rect x="9" y="21" width="8" height="8" rx="1.5" opacity=".55"/><rect x="21" y="21" width="8" height="8" rx="1.5"/></g></svg>"""

APP_CSS = """
<style>
.block-container{padding-top:2rem;max-width:1500px}
.pf-hero{padding:1.4rem 1.6rem;border:1px solid #232a3b;border-radius:14px;margin-bottom:1.2rem;
 background:radial-gradient(1200px 300px at 0% 0%,rgba(124,156,255,.14),transparent 60%),linear-gradient(180deg,#121722,#0f131c)}
.pf-brand{display:flex;align-items:center;gap:.8rem}
.pf-brand h1{margin:0;font-size:1.9rem;letter-spacing:-.02em;padding:0}
.pf-tag{color:#9aa4b8;margin:.5rem 0 0;font-size:1.02rem;max-width:60rem}
.pf-chips{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.8rem}
.pf-chip{font-size:.78rem;color:#aab4c8;border:1px solid #2a3142;border-radius:999px;padding:.15rem .65rem}
.pf-card{border:1px solid #232a3b;border-radius:12px;padding:1rem 1.1rem;background:#0f131c;height:100%}
.pf-card b{color:#7c9cff}
.pf-empty{border:1px dashed #2a3142;border-radius:12px;padding:2rem 1.4rem;color:#9aa4b8;text-align:center}
</style>
"""

logger = get_logger("app")


def render_header(settings: Settings) -> None:
    """Logo, tagline and privacy/safety disclosure."""
    st.markdown(
        f"""<div class="pf-hero"><div class="pf-brand">{LOGO_SVG}<h1>PixelForge</h1></div>
<p class="pf-tag">Turn a UI screenshot into clean, responsive HTML, CSS and JavaScript. Preview it live,
edit the code, and download a ready-to-run project.</p>
<div class="pf-chips"><span class="pf-chip">v{__version__}</span><span class="pf-chip">Sandboxed preview</span>
<span class="pf-chip">No code executed on the server</span><span class="pf-chip">Open source · MIT</span></div></div>""",
        unsafe_allow_html=True,
    )
    st.info(
        f"**Privacy:** when you click *Generate*, your screenshot and instructions are sent to **{settings.provider_host}** "
        f"(model `{settings.model}`) for processing. The offline demo never calls an API. "
        "**Generated code is untrusted: review and test it before deploying.**",
        icon="🔒",
    )


def render_sidebar(ws: Workspace, base: Settings) -> GenerationOptions:
    """Sidebar controls; returns the chosen options."""
    with st.sidebar:
        st.markdown(f"{LOGO_SVG}", unsafe_allow_html=True)
        st.header("Generation settings")
        framework = st.selectbox("Target framework", list(Framework), format_func=lambda f: f.label, help="React output is on the roadmap and not yet available.")
        viewport = st.selectbox("Screenshot viewport", list(Viewport), format_func=lambda v: v.label, help="The viewport the screenshot was captured at.")
        fidelity_name = st.select_slider("Fidelity", options=[f.value for f in Fidelity], value=Fidelity.BALANCED.value, help="Higher detail costs more tokens and time.")
        instructions = st.text_area(
            "Extra instructions (optional)",
            max_chars=1000,
            placeholder="e.g. Use Tailwind-like utility styling without Tailwind. Make it mobile responsive.",
        )
        st.divider()
        st.header("Model & API")
        st.caption(f"Model: `{base.model}`  \nProvider: `{base.provider_host}`")
        ws.session_api_key = st.text_input(
            "Session API key (optional)",
            value=ws.session_api_key,
            type="password",
            help="Kept in memory for this browser session only. Prefer OPENAI_API_KEY in .env.",
        )
        effective = base.with_api_key(ws.session_api_key)
        if effective.has_api_key:
            st.success("API key configured", icon="✅")
        else:
            st.warning("No API key: demo mode only", icon="⚠️")
        st.divider()
        if st.button("Clear workspace", width="stretch", icon="🗑️", help="Remove the screenshot, generated code and messages."):
            ws.reset()
            st.rerun()
    return GenerationOptions(framework=framework, viewport=viewport, fidelity=Fidelity(fidelity_name), instructions=instructions)


def run_generation(ws: Workspace, settings: Settings, options: GenerationOptions) -> None:
    """Call the model, storing either the project or a user-safe error in the workspace."""
    assert ws.image is not None
    ws.error = None
    with st.status("Generating code…", expanded=True) as status:
        try:
            st.write(f"Sending the screenshot to `{settings.model}`. This can take up to a minute.")
            project = generate_code(ws.image, options, settings)
            ws.set_project(project, SOURCE_AI, settings.model)
            ws.flash = f"Generated {len(project.files)} files. Review the preview and code below."
            status.update(label="Done", state="complete", expanded=False)
        except PixelForgeError as exc:
            ws.error = exc.user_message
            status.update(label="Generation failed", state="error", expanded=False)
        except Exception:  # noqa: BLE001 - last-resort guard so the app never crashes
            logger.exception("Unexpected error during generation")
            ws.error = "Something unexpected went wrong. Check the terminal log (secrets are redacted) and try again."
            status.update(label="Generation failed", state="error", expanded=False)


def render_missing_key_help() -> None:
    st.warning(
        "**No API key configured.** Copy `.env.example` to `.env`, set `OPENAI_API_KEY`, and restart the app, "
        "or paste a session key in the sidebar. Meanwhile, the offline demo works without a key.",
        icon="🔑",
    )


def render_input_column(ws: Workspace, settings: Settings, options: GenerationOptions) -> None:
    st.subheader("1 · Screenshot")
    render_uploader(ws, settings)
    if ws.image is None:
        st.caption("Upload a PNG, JPG or WebP screenshot, or try the offline demo below.")
    elif not settings.has_api_key:
        render_missing_key_help()
    label = "Regenerate" if ws.project_source == SOURCE_AI else "Generate code"
    if st.button(label, type="primary", width="stretch", icon="✨", disabled=ws.image is None or not settings.has_api_key,
                 help="Analyse the screenshot with the configured vision model."):
        run_generation(ws, settings, options)
        st.rerun()  # refresh button labels and result column from the saved workspace state
    if st.button("Try the offline demo (no API call)", width="stretch", icon="🧪", help="Loads a sample screenshot with hand-written, pre-made output."):
        try:
            ws.load_demo(settings)
            st.rerun()
        except PixelForgeError as exc:
            ws.error = exc.user_message


def render_download_bar(ws: Workspace) -> None:
    assert ws.project is not None
    try:
        archive = build_zip(ws.project)
    except ExportError as exc:
        st.error(exc.user_message, icon="🚫")
        return
    st.download_button("Download project (.zip)", archive, f"{slugify(ws.project.title)}.zip", "application/zip",
                       type="primary", icon="📦", key=f"zip-{ws.revision}", help="All files plus a README with run instructions.")


def render_files_tab(ws: Workspace) -> None:
    assert ws.project is not None
    st.markdown("**Project files**")
    for path, content in sorted(ws.project.files.items()):
        cols = st.columns([4, 2, 2])
        cols[0].code(path, language=None)
        cols[1].caption(f"{len(content.encode('utf-8')) / 1024:.1f} KB")
        cols[2].download_button("Download", content, path.rsplit("/", 1)[-1], "text/plain", key=f"dl-{ws.revision}-{path}")
    if ws.project.notes:
        st.markdown("**Generator notes**")
        st.write(ws.project.notes)
    if ws.project.warnings:
        with st.expander(f"Sanitiser warnings ({len(ws.project.warnings)})"):
            for warning in ws.project.warnings:
                st.write(f"- {warning}")
    st.caption("The ZIP also contains a README.md with exact run instructions. Edits made in the code tabs are included.")


def render_result_column(ws: Workspace, options: GenerationOptions) -> None:
    st.subheader("2 · Result")
    if ws.flash:
        st.success(ws.flash, icon="✅")
        ws.flash = None
    if ws.error:
        st.error(ws.error, icon="🚨")
    if ws.project is None:
        st.markdown(
            '<div class="pf-empty"><b>Nothing generated yet.</b><br>Upload a screenshot and press <i>Generate code</i>, '
            "or load the offline demo to explore the editor, preview and export.</div>",
            unsafe_allow_html=True,
        )
        return
    if ws.project_source == SOURCE_DEMO:
        st.info("**Demo output:** pre-written sample code for the built-in screenshot. It was *not* produced by an AI model.", icon="🧪")
    else:
        st.caption(f"Generated with `{ws.model_used}`. AI output is an approximation: verify text, colours and behaviour.")
    download_slot = st.container()
    preview_tab, html_tab, css_tab, js_tab, files_tab = st.tabs(["Preview", "HTML", "CSS", "JavaScript", "Files"])
    # Editors run first so that edits made in this rerun are reflected in the preview and ZIP.
    with html_tab:
        render_code_tab(ws, ".html", "No HTML files.")
    with css_tab:
        render_code_tab(ws, ".css", "This project has no CSS files.")
    with js_tab:
        render_code_tab(ws, ".js", "This project has no JavaScript files.")
    with preview_tab:
        render_preview(ws, options.viewport)
    with files_tab:
        render_files_tab(ws)
    with download_slot:
        render_download_bar(ws)


def render_how_it_works() -> None:
    with st.expander("How it works & tips", expanded=False):
        steps = [
            ("1 · Upload", "Drop a PNG, JPG or WebP screenshot. It is validated and downscaled locally."),
            ("2 · Generate", "A vision model returns structured JSON with HTML, CSS and JS files."),
            ("3 · Sanitise", "Paths, sizes and remote references are checked before anything is shown."),
            ("4 · Preview & edit", "The page runs in a locked-down sandbox. Edit code and the preview updates."),
            ("5 · Export", "Download a ZIP with all files and a README."),
        ]
        for col, (title, text) in zip(st.columns(len(steps)), steps, strict=True):
            col.markdown(f'<div class="pf-card"><b>{title}</b><br><span style="color:#9aa4b8">{text}</span></div>', unsafe_allow_html=True)
        st.markdown(
            "- Crop screenshots to the area you want rebuilt; smaller images are faster and cheaper.\n"
            "- Choose the viewport the screenshot was captured at so the layout is matched first.\n"
            "- Photos become neutral placeholders: the output never loads external assets.\n"
            "- Use *Extra instructions* for style preferences, e.g. \"use CSS custom properties for the palette\"."
        )


def main() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)
    try:
        base_settings = load_settings()
    except ConfigError as exc:
        st.error(f"Configuration problem: {exc.user_message}", icon="⚙️")
        st.stop()
    setup_logging(base_settings.log_level)
    ws = get_workspace()
    options = render_sidebar(ws, base_settings)
    settings = base_settings.with_api_key(ws.session_api_key)
    render_header(settings)
    left, right = st.columns(2, gap="large")
    with left:
        render_input_column(ws, settings, options)
    with right:
        render_result_column(ws, options)
    render_how_it_works()


main()
