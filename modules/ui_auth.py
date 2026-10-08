"""
VERIDEXA landing page, sign up, and login screens.
This is the very first thing an unauthenticated visitor sees.

Now with a real interactive 3D hero (Three.js  drag to orbit, it also
auto-rotates), animated counters, and mouse-tilt 3D feature cards.
"""
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from config.settings import APP_NAME, APP_TAGLINE
from modules.auth import AuthError, login, signup

LANDING_CSS = """
<style>
#MainMenu, footer, header {visibility: hidden;}

@keyframes vx-border-glow {
    0%   { border-color: #6C5CE7; box-shadow: 0 0 0px rgba(108,92,231,0.0); }
    50%  { border-color: #34D6C4; box-shadow: 0 0 22px rgba(52,214,196,0.25); }
    100% { border-color: #6C5CE7; box-shadow: 0 0 0px rgba(108,92,231,0.0); }
}
@keyframes vx-fade-up {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}

div[data-testid="stForm"] {
    background: rgba(23,26,35,0.75);
    backdrop-filter: blur(10px);
    border: 1px solid #2A2E40;
    border-radius: 18px;
    padding: 1.7rem 1.7rem 0.9rem 1.7rem;
    animation: vx-border-glow 4.5s ease-in-out infinite, vx-fade-up 0.5s ease-out;
}
div[data-testid="stForm"] button[kind="primary"] {
    background: linear-gradient(90deg, #6C5CE7 0%, #8A7CFF 50%, #34D6C4 100%);
    background-size: 200% auto;
    border: none;
    transition: background-position 0.4s ease, transform 0.15s ease;
}
div[data-testid="stForm"] button[kind="primary"]:hover {
    background-position: right center;
    transform: translateY(-1px);
}
.vx-footer-note {text-align:center; color:#6B6E82; font-size:0.78rem; margin-top: 1.6rem;
                  animation: vx-fade-up 0.6s ease-out;}
</style>
"""

FEATURES = [
    ("📂", "Upload & Clean", "Drop in a CSV or Excel file and get instant validation, missing-value and duplicate detection, and one-click cleaning."),
    ("🤖", "AI Analyst", "Ask questions in plain English. Every number comes from real Pandas/SQL execution never a guessed figure."),
    ("🔮", "Forecasting", "Explainable trend projections with confidence bands, so you know what's a forecast and what's a fact."),
    ("⚠️", "Anomaly Detection", "IQR-based outlier flags with plain-language reasons for every flagged record."),
    ("👥", "Segmentation", "RFM and K-Means customer segmentation with AI-written explanations of each group."),
    ("🧊", "3D Data Explorer", "Rotate, zoom, and fly through your own data as an interactive 3D scatter or surface not a static screenshot."),
]

STATS = [
    ("50", "+", "Built-in analyses"),
    ("100", "%", "Real computation, 0 hallucinated numbers"),
    ("0", "", "API keys required to start"),
]


def _inject_css():
    st.markdown(LANDING_CSS, unsafe_allow_html=True)


def render_3d_hero():
    """A real, rendered, auto-rotating (and drag-to-orbit) Three.js 3D scene
    a glowing icosahedron core wrapped in an orbiting particle data-swarm
    with the app title/tagline overlaid on top. This is genuine WebGL 3D,
    not a CSS illusion."""
    html = f"""
    <div id="vx-hero-wrap" style="position:relative; width:100%; height:380px;
         border-radius:20px; overflow:hidden; background:radial-gradient(ellipse at 50% 0%, #1B1E2C 0%, #0E0F16 70%);
         font-family: sans-serif;">
      <canvas id="vx-canvas" style="position:absolute; inset:0; width:100%; height:100%; cursor:grab;"></canvas>
      <div style="position:absolute; inset:0; display:flex; flex-direction:column;
                  align-items:center; justify-content:center; text-align:center;
                  pointer-events:none; padding: 0 1rem;">
        <div style="font-size:2.7rem; font-weight:800; letter-spacing:0.05em;
                    background:linear-gradient(90deg,#8A7CFF 0%,#6C5CE7 45%,#34D6C4 100%);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                    text-shadow:0 0 40px rgba(108,92,231,0.35);">
          {APP_NAME}
        </div>
        <div style="color:#C7C9DA; font-size:1.05rem; margin-top:0.2rem;">{APP_TAGLINE}</div>
        <div style="display:flex; gap:0.6rem; margin-top:1rem; flex-wrap:wrap; justify-content:center;">
          <span style="background:rgba(27,30,42,0.85); border:1px solid #2A2E40; color:#C7C9DA;
                       padding:0.28rem 0.75rem; border-radius:999px; font-size:0.78rem;">🔒 Real computation, not LLM guesses</span>
          <span style="background:rgba(27,30,42,0.85); border:1px solid #2A2E40; color:#C7C9DA;
                       padding:0.28rem 0.75rem; border-radius:999px; font-size:0.78rem;">🧊 Live 3D exploration</span>
          <span style="background:rgba(27,30,42,0.85); border:1px solid #2A2E40; color:#C7C9DA;
                       padding:0.28rem 0.75rem; border-radius:999px; font-size:0.78rem;">⚡ Instant profiling</span>
        </div>
        <div style="color:#5C5F73; font-size:0.72rem; margin-top:0.9rem;">drag to orbit ↻</div>
      </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
    (function() {{
      const wrap = document.getElementById('vx-hero-wrap');
      const canvas = document.getElementById('vx-canvas');
      const w = wrap.clientWidth, h = wrap.clientHeight;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 1000);
      camera.position.set(0, 0, 9);

      const renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true }});
      renderer.setSize(w, h, false);
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

      // Glowing wireframe icosahedron core
      const coreGeo = new THREE.IcosahedronGeometry(2.1, 1);
      const coreMat = new THREE.MeshBasicMaterial({{ color: 0x6C5CE7, wireframe: true, transparent: true, opacity: 0.85 }});
      const core = new THREE.Mesh(coreGeo, coreMat);
      scene.add(core);

      const coreGlowGeo = new THREE.IcosahedronGeometry(2.05, 1);
      const coreGlowMat = new THREE.MeshBasicMaterial({{ color: 0x34D6C4, wireframe: true, transparent: true, opacity: 0.25 }});
      const coreGlow = new THREE.Mesh(coreGlowGeo, coreGlowMat);
      scene.add(coreGlow);

      // Orbiting particle "data swarm"
      const N = 420;
      const positions = new Float32Array(N * 3);
      const colorsArr = new Float32Array(N * 3);
      const palette = [[0.42,0.36,0.91], [0.20,0.84,0.77], [1.0,0.49,0.70]];
      for (let i = 0; i < N; i++) {{
        const r = 3.2 + Math.random() * 2.6;
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos((Math.random() * 2) - 1);
        positions[i*3]   = r * Math.sin(phi) * Math.cos(theta);
        positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta) * 0.6;
        positions[i*3+2] = r * Math.cos(phi);
        const c = palette[i % palette.length];
        colorsArr[i*3] = c[0]; colorsArr[i*3+1] = c[1]; colorsArr[i*3+2] = c[2];
      }}
      const particleGeo = new THREE.BufferGeometry();
      particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      particleGeo.setAttribute('color', new THREE.BufferAttribute(colorsArr, 3));
      const particleMat = new THREE.PointsMaterial({{ size: 0.065, vertexColors: true, transparent: true, opacity: 0.9 }});
      const particles = new THREE.Points(particleGeo, particleMat);
      scene.add(particles);

      // Drag-to-orbit interaction
      let dragging = false, lastX = 0, lastY = 0;
      let rotX = 0.3, rotY = 0;
      canvas.addEventListener('pointerdown', (e) => {{ dragging = true; lastX = e.clientX; lastY = e.clientY; canvas.style.cursor = 'grabbing'; }});
      window.addEventListener('pointerup', () => {{ dragging = false; canvas.style.cursor = 'grab'; }});
      window.addEventListener('pointermove', (e) => {{
        if (!dragging) return;
        rotY += (e.clientX - lastX) * 0.005;
        rotX += (e.clientY - lastY) * 0.005;
        lastX = e.clientX; lastY = e.clientY;
      }});

      let t = 0;
      function animate() {{
        requestAnimationFrame(animate);
        t += 0.01;
        if (!dragging) {{ rotY += 0.0022; }}
        core.rotation.y = rotY; core.rotation.x = rotX + Math.sin(t*0.3)*0.05;
        coreGlow.rotation.y = -rotY * 0.6; coreGlow.rotation.x = rotX;
        particles.rotation.y = rotY * 0.4;
        particles.rotation.x = rotX * 0.4;
        const pulse = 1 + Math.sin(t * 1.4) * 0.04;
        core.scale.set(pulse, pulse, pulse);
        renderer.render(scene, camera);
      }}
      animate();

      window.addEventListener('resize', () => {{
        const nw = wrap.clientWidth, nh = wrap.clientHeight;
        camera.aspect = nw / nh; camera.updateProjectionMatrix();
        renderer.setSize(nw, nh, false);
      }});
    }})();
    </script>
    """
    components.html(html, height=390)


def render_feature_grid():
    """Feature cards with genuine JS-driven 3D perspective tilt that follows
    the mouse (not just a CSS :hover), plus animated count-up stat badges."""
    cards_html = ""
    for icon, title, desc in FEATURES:
        cards_html += f"""
        <div class="vx-tilt-card">
          <div class="vx-tilt-inner">
            <div class="vx-feature-title">{icon} {title}</div>
            <div class="vx-feature-desc">{desc}</div>
          </div>
        </div>
        """

    stats_html = ""
    for i, (num, suffix, label) in enumerate(STATS):
        stats_html += f"""
        <div class="vx-stat">
          <div class="vx-stat-num"><span id="vx-stat-{i}">0</span>{suffix}</div>
          <div class="vx-stat-label">{label}</div>
        </div>
        """

    html = f"""
    <div style="font-family:sans-serif;">
    <style>
      .vx-stats-row {{ display:flex; gap:1.2rem; justify-content:center; margin-bottom:1.4rem; flex-wrap:wrap; }}
      .vx-stat {{ text-align:center; }}
      .vx-stat-num {{ font-size:1.7rem; font-weight:800;
                      background:linear-gradient(90deg,#8A7CFF,#34D6C4);
                      -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
      .vx-stat-label {{ color:#9294A6; font-size:0.75rem; max-width:150px; margin:0 auto; }}

      .vx-grid {{ display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem; perspective: 1000px; }}
      @media (max-width: 900px) {{ .vx-grid {{ grid-template-columns: repeat(1, 1fr); }} }}
      .vx-tilt-card {{
        background:#171A23; border:1px solid #262A38; border-radius:14px;
        padding:1.1rem 1.2rem; transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.2s ease;
        transform-style: preserve-3d; will-change: transform;
      }}
      .vx-tilt-card:hover {{ border-color:#3D3F63; box-shadow: 0 14px 30px rgba(108,92,231,0.22); }}
      .vx-feature-title {{ font-weight:700; font-size:0.98rem; margin-bottom:0.3rem; color:#F0F0F5; transform: translateZ(20px); }}
      .vx-feature-desc {{ color:#A7A9BC; font-size:0.85rem; line-height:1.4rem; transform: translateZ(10px); }}
    </style>

    <div class="vx-stats-row">{stats_html}</div>
    <div class="vx-grid" id="vx-grid">{cards_html}</div>
    </div>

    <script>
    (function() {{
      // 3D pointer-tracking tilt
      const cards = document.querySelectorAll('.vx-tilt-card');
      cards.forEach((card) => {{
        card.addEventListener('mousemove', (e) => {{
          const r = card.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width;
          const py = (e.clientY - r.top) / r.height;
          const rotY = (px - 0.5) * 16;
          const rotX = (0.5 - py) * 16;
          card.style.transform = `perspective(800px) rotateX(${{rotX}}deg) rotateY(${{rotY}}deg) scale3d(1.02,1.02,1.02)`;
        }});
        card.addEventListener('mouseleave', () => {{
          card.style.transform = 'perspective(800px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)';
        }});
      }});

      // Animated count-up stats
      const targets = {[float(n) for n, _, _ in STATS]};
      targets.forEach((target, i) => {{
        const el = document.getElementById('vx-stat-' + i);
        const duration = 1100;
        const start = performance.now();
        function step(now) {{
          const t = Math.min(1, (now - start) / duration);
          const eased = 1 - Math.pow(1 - t, 3);
          el.textContent = Math.round(target * eased).toLocaleString();
          if (t < 1) requestAnimationFrame(step);
        }}
        requestAnimationFrame(step);
      }});
    }})();
    </script>
    """
    components.html(html, height=470, scrolling=False)


def _login_form():
    with st.form("login_form", clear_on_submit=False):
        st.subheader("Welcome back")
        identifier = st.text_input("Username or email", key="login_identifier")
        password = st.text_input("Password", type="password", key="login_password")
        remember = st.checkbox("Keep me signed in on this device", value=True)
        submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")

        if submitted:
            try:
                user = login(identifier, password)
                st.session_state.auth_user = {
                    "id": user.id, "username": user.username,
                    "email": user.email, "full_name": user.full_name,
                }
                st.session_state.authenticated = True
                st.session_state.remember_me = remember
                st.session_state.login_time = datetime.utcnow()
                st.session_state.page = "app"
                st.success(f"Welcome back, {user.username}!")
                st.rerun()
            except AuthError as e:
                st.error(str(e))

    with st.container():
        st.caption("New to VERIDEXA?")
        if st.button("Create an account instead →", use_container_width=True):
            st.session_state.auth_view = "signup"
            st.rerun()


def _signup_form():
    with st.form("signup_form", clear_on_submit=False):
        st.subheader("Create your account")
        c1, c2 = st.columns(2)
        with c1:
            username = st.text_input("Username", key="signup_username",
                                      help="3-24 characters: letters, numbers, underscore.")
        with c2:
            full_name = st.text_input("Full name (optional)", key="signup_fullname")
        email = st.text_input("Email", key="signup_email")
        c3, c4 = st.columns(2)
        with c3:
            password = st.text_input("Password", type="password", key="signup_password")
        with c4:
            confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
        st.caption("Minimum 8 characters, with an uppercase letter, lowercase letter, and number.")
        agree = st.checkbox("I agree with this app and my data is stored locally.")
        submitted = st.form_submit_button("Create account", use_container_width=True, type="primary")

        if submitted:
            if not agree:
                st.error("Please confirm the checkbox above to continue.")
            else:
                try:
                    user = signup(username, email, password, confirm, full_name)
                    st.session_state.auth_user = {
                        "id": user.id, "username": user.username,
                        "email": user.email, "full_name": user.full_name,
                    }
                    st.session_state.authenticated = True
                    st.session_state.login_time = datetime.utcnow()
                    st.session_state.page = "app"
                    st.success(f"Account created welcome, {user.username}!")
                    st.rerun()
                except AuthError as e:
                    st.error(str(e))

    st.caption("Already have an account?")
    if st.button("Log in instead →", use_container_width=True):
        st.session_state.auth_view = "login"
        st.rerun()


def render_auth_page():
    _inject_css()
    render_3d_hero()
    st.write("")
    render_feature_grid()

    st.write("")
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        view = st.session_state.get("auth_view", "login")
        if view == "signup":
            _signup_form()
        else:
            _login_form()

    st.markdown(
        f'<div class="vx-footer-note">{APP_NAME} a analytics engine. '
        f"Your data stays in your local session database.</div>",
        unsafe_allow_html=True,
    )
