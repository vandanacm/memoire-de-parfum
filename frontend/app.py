import re
import streamlit as st
import httpx

# ─── Constants ────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
FRAGRANCE_TIMEOUT = 180.0
REFINE_TIMEOUT = 120.0

WELCOME_MESSAGE = (
    "Welcome to **Mémoire de Parfum** — where memories become fragrance.\n\n"
    "I'll guide you through creating a personalized scent composition. "
    "Every fragrance tells a story — let's write yours.\n\n"
    "Would you like to create a fragrance inspired by your **past**, "
    "your **present**, or your **future**?"
)

FRAME_INTROS = {
    "past": (
        "Beautiful choice. Let's recreate a cherished memory. "
        "I'll ask you a few questions to capture its essence."
    ),
    "present": (
        "Wonderful. Let's create a fragrance that expresses who you are right now. "
        "I'll guide you through a few questions."
    ),
    "future": (
        "Lovely. Let's design a fragrance for a moment yet to come. "
        "A few questions will help me shape the vision."
    ),
}

FRAME_QUESTIONS = {
    "past": [
        {
            "key": "memory_description",
            "prompt": (
                "Tell me about the memory you'd like to relive. "
                "The place, the people, the moment — whatever comes to mind."
            ),
            "type": "text",
        },
        {
            "key": "emotions",
            "prompt": "What emotions feel strongest when you recall this memory?",
            "type": "multi",
            "options": [
                ("comfort", "Comfort"),
                ("joy", "Joy"),
                ("nostalgia", "Nostalgia"),
                ("peace", "Peace"),
                ("love", "Love"),
                ("excitement", "Excitement"),
            ],
        },
        {
            "key": "air_texture",
            "prompt": "Think back to that moment. How did the air feel around you?",
            "type": "single",
            "options": [
                ("warm", "Warm"),
                ("fresh", "Fresh"),
                ("humid", "Humid"),
                ("dry", "Dry"),
            ],
        },
        {
            "key": "scent_hints",
            "prompt": "Did you notice any particular scents in that memory?",
            "type": "multi",
            "options": [
                ("floral", "Floral"),
                ("sweet", "Sweet"),
                ("green", "Green"),
                ("earthy", "Earthy"),
                ("clean", "Clean"),
                ("unclear", "Not sure"),
            ],
        },
        {
            "key": "intensity_memory",
            "prompt": "How intense was the scent of that moment?",
            "type": "single",
            "options": [
                ("soft", "Soft"),
                ("gentle", "Gentle"),
                ("rich", "Rich"),
            ],
        },
        {
            "key": "skin_sensitivity",
            "prompt": "Last question — how would you describe your skin's sensitivity?",
            "type": "single",
            "options": [
                ("very_gentle", "Very gentle"),
                ("balanced", "Balanced"),
                ("expressive", "Expressive"),
            ],
        },
    ],
    "present": [
        {
            "key": "life_chapter",
            "prompt": "How would you describe the chapter of life you're in right now?",
            "type": "single",
            "options": [
                ("fast_paced", "Fast-paced"),
                ("balanced", "Balanced"),
                ("explorative", "Explorative"),
                ("grounded", "Grounded"),
                ("transformative", "Transformative"),
            ],
        },
        {
            "key": "daily_feeling",
            "prompt": "When you wear this fragrance, how do you want to feel?",
            "type": "multi",
            "options": [
                ("confident", "Confident"),
                ("calm", "Calm"),
                ("energized", "Energized"),
                ("elegant", "Elegant"),
                ("powerful", "Powerful"),
            ],
        },
        {
            "key": "scent_direction",
            "prompt": "What scent direction draws you most?",
            "type": "single",
            "options": [
                ("fresh_citrus", "Fresh citrus"),
                ("woody", "Woody"),
                ("floral", "Floral"),
                ("musky", "Musky"),
                ("warm_spicy", "Warm & spicy"),
            ],
        },
        {
            "key": "social_context",
            "prompt": "What will this fragrance mainly be for?",
            "type": "single",
            "options": [
                ("work", "Work"),
                ("everyday", "Everyday"),
                ("evening", "Evening"),
            ],
        },
        {
            "key": "projection",
            "prompt": "How far should your scent carry?",
            "type": "single",
            "options": [
                ("skin_close", "Skin-close"),
                ("balanced", "Balanced"),
                ("statement", "A bold statement"),
            ],
        },
    ],
    "future": [
        {
            "key": "future_moment",
            "prompt": "What is this future fragrance for? What occasion or milestone?",
            "type": "single",
            "options": [
                ("wedding", "A wedding"),
                ("career_milestone", "A career milestone"),
                ("travel", "Travel"),
                ("personal_transformation", "Personal transformation"),
                ("new_chapter", "A new chapter"),
            ],
        },
        {
            "key": "emotional_intention",
            "prompt": "How do you want to feel in that moment?",
            "type": "multi",
            "options": [
                ("radiant", "Radiant"),
                ("empowered", "Empowered"),
                ("emotional", "Emotional"),
                ("grounded", "Grounded"),
                ("confident", "Confident"),
            ],
        },
        {
            "key": "desired_impression",
            "prompt": "When others encounter this fragrance, what should they sense?",
            "type": "multi",
            "options": [
                ("memorable", "Memorable"),
                ("intimate", "Intimate"),
                ("elegant", "Elegant"),
                ("bold", "Bold"),
                ("timeless", "Timeless"),
            ],
        },
        {
            "key": "scent_imagination",
            "prompt": "If you imagine this moment as a scent, how does it feel?",
            "type": "single",
            "options": [
                ("soft_floral", "Soft & floral"),
                ("fresh_luminous", "Fresh & luminous"),
                ("warm_comforting", "Warm & comforting"),
                ("deep_woody", "Deep & woody"),
            ],
        },
        {
            "key": "longevity",
            "prompt": "How long should the fragrance last?",
            "type": "single",
            "options": [
                ("subtle", "Subtle"),
                ("evolving", "Evolving"),
                ("lasting", "Lasting"),
            ],
        },
    ],
}

REFINEMENT_MAP = {
    "lighter": "Lighter",
    "stronger": "Stronger",
    "warmer": "Warmer",
    "fresher": "Fresher",
}


# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Mémoire de Parfum",
    page_icon="🌸",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ─── Session State ────────────────────────────────────────────────────────────

_DEFAULTS = {
    "messages": [],
    "phase": "greeting",
    "memory_frame": None,
    "answers": {},
    "q_idx": 0,
    "intent": None,
    "blueprint": None,
    "fragrance_story": None,
    "refinement_count": 0,
    "free_text": "",
    "_action": None,
    "_multi_selected": [],
    "_pending_refinement": None,
    "dark_mode": True,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v.copy() if isinstance(_v, (list, dict)) else _v


# ─── Theme CSS ────────────────────────────────────────────────────────────────

_dark = st.session_state.dark_mode

_LIGHT = """
    --bg: #ffffff;
    --bg-alt: #f0f0f0;
    --bg-card: #f5f5f5;
    --bg-note: #fafafa;
    --bg-input: #f4f4f4;
    --text: #111111;
    --text-secondary: #555555;
    --text-muted: #999999;
    --border: #e0e0e0;
    --border-strong: #cccccc;
    --accent: #8b6f47;
    --dot: #999999;
    --shadow: 0 1px 3px rgba(0,0,0,0.06);
    --user-bubble: #111111;
    --user-text: #ffffff;
    --ai-bubble: #f0f0f0;
    --ai-text: #111111;
    --btn-bg: #f4f4f4;
    --btn-text: #111111;
    --btn-border: #d0d0d0;
    --btn-hover-bg: #111111;
    --btn-hover-text: #ffffff;
"""

_DARK = """
    --bg: #1a1a1a;
    --bg-alt: #262626;
    --bg-card: #262626;
    --bg-note: #2e2e2e;
    --bg-input: #262626;
    --text: #e8e8e8;
    --text-secondary: #aaaaaa;
    --text-muted: #777777;
    --border: #333333;
    --border-strong: #444444;
    --accent: #c4a06a;
    --dot: #777777;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
    --user-bubble: #c4a06a;
    --user-text: #111111;
    --ai-bubble: #262626;
    --ai-text: #e8e8e8;
    --btn-bg: #2e2e2e;
    --btn-text: #e8e8e8;
    --btn-border: #444444;
    --btn-hover-bg: #e8e8e8;
    --btn-hover-text: #1a1a1a;
"""

_AI_SVG = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 2L15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 '
    '5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2z"/></svg>'
)
_USER_SVG = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">'
    '<path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 '
    '7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>'
)

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

:root {{ {_DARK if _dark else _LIGHT} }}

/* ── Reset ─────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [class*="css"],
p, li, span, label, div, input, textarea, button {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

h1, h2, h3, h4 {{
    font-family: 'Inter', -apple-system, sans-serif !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}}

/* ── Hide Streamlit chrome ─────────────────────────────── */
#MainMenu, footer, header,
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stToolbar"] {{
    display: none !important;
    visibility: hidden !important;
}}

/* ── Full-page background ──────────────────────────────── */
html, body {{ background-color: var(--bg) !important; }}

.stApp, .stApp > *,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > *,
.stMainBlockContainer,
[data-testid="stVerticalBlock"],
.block-container,
section[data-testid="stMain"],
section[data-testid="stMain"] > div {{
    background-color: var(--bg) !important;
    color: var(--text) !important;
}}

/* ── Bottom bar ────────────────────────────────────────── */
[data-testid="stBottom"],
[data-testid="stBottom"] > *,
[data-testid="stBottomBlockContainer"],
[data-testid="stBottomBlockContainer"] > *,
.stChatFloatingInputContainer,
.stChatFloatingInputContainer > * {{
    background: var(--bg) !important;
    background-color: var(--bg) !important;
    border: none !important;
    box-shadow: none !important;
}}

/* ── Chat input: outer wrapper transparent ─────────────── */
[data-testid="stChatInput"] {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
}}

/* ── Chat input: inner styled box ──────────────────────── */
[data-testid="stChatInput"] > div {{
    background: var(--bg-input) !important;
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border) !important;
    border-radius: 24px !important;
    box-shadow: none !important;
    outline: none !important;
}}

[data-testid="stChatInput"] > div > div {{
    background: transparent !important;
    background-color: transparent !important;
}}

[data-testid="stChatInput"] textarea {{
    color: var(--text) !important;
    caret-color: var(--text) !important;
    background: transparent !important;
    background-color: transparent !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: var(--text-muted) !important;
}}

[data-testid="stChatInput"] button {{
    color: var(--text-muted) !important;
    background: transparent !important;
}}
[data-testid="stChatInput"] button:hover {{
    color: var(--text) !important;
}}

/* ── Hide default st.chat_message (only used for typing) ─ */
.stChatMessage {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
}}
[data-testid="stChatMessage"] {{
    background: transparent !important;
}}
.stChatMessage [data-testid="stAvatar"],
.stChatMessage [data-testid="stAvatarIcon"] {{
    display: none !important;
}}

/* ── Chat bubble layout ────────────────────────────────── */
.chat-row {{
    display: flex;
    gap: 10px;
    margin-bottom: 6px;
    align-items: flex-start;
    padding: 0 4px;
}}
.ai-row {{
    justify-content: flex-start;
}}
.user-row {{
    justify-content: flex-end;
}}

/* ── Avatars ───────────────────────────────────────────── */
.av {{
    width: 30px;
    height: 30px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
}}
.av-ai {{
    background: var(--accent);
    color: #ffffff;
}}
.av-user {{
    background: var(--user-bubble);
    color: var(--user-text);
}}

/* ── Bubbles ───────────────────────────────────────────── */
.bubble {{
    padding: 10px 16px;
    border-radius: 20px;
    font-size: 0.88rem;
    line-height: 1.65;
    word-wrap: break-word;
    overflow-wrap: break-word;
}}
.ai-bubble {{
    background: var(--ai-bubble);
    color: var(--ai-text);
    border-bottom-left-radius: 6px;
    max-width: 82%;
}}
.ai-bubble p, .ai-bubble span, .ai-bubble li,
.ai-bubble strong, .ai-bubble em, .ai-bubble b, .ai-bubble i,
.ai-bubble a, .ai-bubble div {{
    color: var(--ai-text) !important;
}}
.ai-bubble em, .ai-bubble i {{
    color: var(--text-secondary) !important;
}}
.ai-bubble a {{
    color: var(--accent) !important;
}}

.user-bubble {{
    background: var(--user-bubble);
    color: var(--user-text);
    border-bottom-right-radius: 6px;
    max-width: 70%;
}}
.user-bubble, .user-bubble * {{
    color: var(--user-text) !important;
}}

/* ── Fragrance result card ─────────────────────────────── */
.fragrance-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin: 4px 0;
}}
.fragrance-story {{
    font-size: 0.88rem;
    line-height: 1.8;
    color: var(--text-secondary) !important;
    font-style: italic;
    border-left: 3px solid var(--accent);
    padding-left: 1rem;
    margin-bottom: 1.5rem;
}}
.comp-title {{
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text) !important;
    margin-bottom: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.notes-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1rem;
    margin: 1rem 0;
}}
@media (max-width: 640px) {{
    .notes-grid {{ grid-template-columns: 1fr; }}
}}
.note-column h4 {{
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    margin-bottom: 0.15rem;
}}
.note-subtitle {{
    font-size: 0.62rem;
    color: var(--text-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.5rem;
}}
.note-item {{
    background: var(--bg-note);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.4rem 0.6rem;
    margin-bottom: 0.3rem;
}}
.note-name {{
    font-weight: 500;
    color: var(--text) !important;
    font-size: 0.78rem;
}}
.note-detail {{
    font-size: 0.66rem;
    color: var(--text-muted) !important;
    margin-top: 0.08rem;
}}
.note-sub {{
    font-size: 0.62rem;
    color: var(--text-muted) !important;
    font-style: italic;
}}
.details-row {{
    display: flex;
    justify-content: space-around;
    margin: 1rem 0;
    padding: 0.7rem 0;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
}}
.detail {{ text-align: center; }}
.detail-label {{
    display: block;
    font-size: 0.6rem;
    color: var(--text-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.15rem;
}}
.detail-value {{
    display: block;
    font-size: 0.92rem;
    font-weight: 500;
    color: var(--text) !important;
}}
.safety-note {{
    background: var(--bg-alt);
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    font-size: 0.7rem;
    color: var(--text-muted) !important;
    margin-top: 0.7rem;
}}

/* ── Typing indicator ──────────────────────────────────── */
@keyframes typing-bounce {{
    0%, 80%, 100% {{ transform: translateY(0); opacity: 0.25; }}
    40% {{ transform: translateY(-4px); opacity: 1; }}
}}
.typing-wrapper {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 2px 0;
}}
.typing-label {{
    font-size: 0.82rem;
    color: var(--text-muted) !important;
    font-style: italic;
}}
.typing-dots {{
    display: flex;
    align-items: center;
    gap: 4px;
}}
.typing-dots span {{
    display: block;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--dot) !important;
    animation: typing-bounce 1.4s infinite ease-in-out;
}}
.typing-dots span:nth-child(2) {{ animation-delay: 0.2s; }}
.typing-dots span:nth-child(3) {{ animation-delay: 0.4s; }}

/* ── Suggestion buttons ────────────────────────────────── */
.stButton > button {{
    border-radius: 20px !important;
    padding: 0.4rem 1rem !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 400 !important;
    letter-spacing: 0 !important;
    transition: all 0.15s ease !important;
    border: 1px solid var(--btn-border) !important;
    background: var(--btn-bg) !important;
    color: var(--btn-text) !important;
    box-shadow: none !important;
}}
.stButton > button:hover {{
    background: var(--btn-hover-bg) !important;
    color: var(--btn-hover-text) !important;
    border-color: var(--btn-hover-bg) !important;
}}
.stButton > button:active,
.stButton > button:focus {{
    background: var(--btn-hover-bg) !important;
    color: var(--btn-hover-text) !important;
    border-color: var(--btn-hover-bg) !important;
}}

/* ── Header ────────────────────────────────────────────── */
.hdr {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 0 0.5rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.8rem;
}}
.hdr-left {{
    display: flex;
    align-items: baseline;
    gap: 8px;
}}
.hdr-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
}}
.hdr-sub {{
    font-size: 0.68rem;
    color: var(--text-muted);
    font-weight: 400;
}}

/* ── Separator before suggestions ──────────────────────── */
.suggestion-sep {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 0.5rem 0 0.3rem 0;
}}

/* ── Markdown defaults ─────────────────────────────────── */
.stMarkdown, .stMarkdown p, .stMarkdown span {{
    color: var(--text) !important;
}}

/* ── Scrollbar ─────────────────────────────────────────── */
::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: var(--border-strong); }}
</style>
""",
    unsafe_allow_html=True,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helper Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _md(text: str) -> str:
    """Convert simple markdown (bold/italic) to HTML."""
    t = text
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    t = t.replace("\n\n", "<br><br>")
    t = t.replace("\n", "<br>")
    return t


def add_msg(role: str, content: str, html: bool = False):
    st.session_state.messages.append(
        {"role": role, "content": content, "html": html}
    )


def render_bubble(role: str, content: str, is_html: bool = False):
    """Render a single chat bubble as custom HTML."""
    inner = content if is_html else _md(content)

    if role == "assistant":
        st.markdown(
            f'<div class="chat-row ai-row">'
            f'<div class="av av-ai">{_AI_SVG}</div>'
            f'<div class="bubble ai-bubble">{inner}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="chat-row user-row">'
            f'<div class="bubble user-bubble">{inner}</div>'
            f'<div class="av av-user">{_USER_SVG}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def get_current_question():
    frame = st.session_state.memory_frame
    questions = FRAME_QUESTIONS.get(frame, [])
    idx = st.session_state.q_idx
    return questions[idx] if idx < len(questions) else None


def ask_next_question():
    q = get_current_question()
    if q is None:
        st.session_state.phase = "free_text"
        add_msg(
            "assistant",
            "Is there anything else you'd like to share? Any extra details, "
            "feelings, or context that could help capture your vision?\n\n"
            "*Type anything you'd like, or say* ***skip*** *to continue.*",
        )
        return
    add_msg("assistant", q["prompt"])


def match_single(text: str, options: list):
    t = text.lower().strip()
    for v, lbl in options:
        if t == v.lower() or t == lbl.lower():
            return v, lbl
    for v, lbl in options:
        if t in v.lower() or t in lbl.lower() or v.lower() in t or lbl.lower() in t:
            return v, lbl
    return None


def match_multi(text: str, options: list):
    parts = [p.strip() for p in text.replace(", ", ",").split(",")]
    matched = []
    for part in parts:
        m = match_single(part, options)
        if m and m not in matched:
            matched.append(m)
    return matched


def build_payload() -> dict:
    frame = st.session_state.memory_frame
    return {
        "memory_frame": frame,
        frame: st.session_state.answers,
        "free_text_memory": st.session_state.free_text or "",
    }


def format_result_html(blueprint: dict, story: str) -> str:
    def _notes(notes, title, subtitle):
        h = f'<div class="note-column"><h4>{title}</h4>'
        h += f'<p class="note-subtitle">{subtitle}</p>'
        for n in notes:
            sub = (
                ' <span class="note-sub">(substituted)</span>'
                if n.get("is_substituted")
                else ""
            )
            h += (
                f'<div class="note-item">'
                f'<div class="note-name">{n["name"].title()}{sub}</div>'
                f'<div class="note-detail">{n["family"]} &middot; {n["description"]}</div>'
                f"</div>"
            )
        return h + "</div>"

    top = _notes(blueprint.get("top_notes", []), "Top Notes", "First impression")
    heart = _notes(blueprint.get("heart_notes", []), "Heart Notes", "Character")
    base = _notes(blueprint.get("base_notes", []), "Base Notes", "Lasting impression")

    dash = "\u2014"
    shield = "\U0001f6e1\ufe0f"
    intensity = blueprint.get("intensity", dash).title()
    projection = blueprint.get("projection", dash).title()
    longevity = blueprint.get("longevity", dash).title()
    safety = blueprint.get("safety_note", "")

    return (
        '<div class="fragrance-card">'
        f'<div class="fragrance-story">{story}</div>'
        '<h3 class="comp-title">The Composition</h3>'
        f'<div class="notes-grid">{top}{heart}{base}</div>'
        '<div class="details-row">'
        f'<div class="detail"><span class="detail-label">Intensity</span>'
        f'<span class="detail-value">{intensity}</span></div>'
        f'<div class="detail"><span class="detail-label">Projection</span>'
        f'<span class="detail-value">{projection}</span></div>'
        f'<div class="detail"><span class="detail-label">Longevity</span>'
        f'<span class="detail-value">{longevity}</span></div>'
        "</div>"
        f'<div class="safety-note">{shield} {safety}</div>'
        "</div>"
    )


TYPING_HTML_GENERATE = (
    '<div class="typing-wrapper">'
    '<span class="typing-label">Crafting your fragrance</span>'
    '<div class="typing-dots"><span></span><span></span><span></span></div>'
    "</div>"
)
TYPING_HTML_REFINE = (
    '<div class="typing-wrapper">'
    '<span class="typing-label">Refining your fragrance</span>'
    '<div class="typing-dots"><span></span><span></span><span></span></div>'
    "</div>"
)


def render_typing(label_html: str):
    """Render a typing indicator as an AI bubble."""
    st.markdown(
        f'<div class="chat-row ai-row">'
        f'<div class="av av-ai">{_AI_SVG}</div>'
        f'<div class="bubble ai-bubble">{label_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def reset_conversation():
    preserve_dark = st.session_state.dark_mode
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v.copy() if isinstance(v, (list, dict)) else v
    st.session_state.dark_mode = preserve_dark
    add_msg("assistant", WELCOME_MESSAGE)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Action Handlers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _handle_greeting(action):
    atype = action.get("type", "text")
    value = action.get("value", "")

    if atype == "frame":
        frame = value
    else:
        add_msg("user", value)
        text_l = value.lower().strip()
        frame = None
        if "past" in text_l:
            frame = "past"
        elif "present" in text_l:
            frame = "present"
        elif "future" in text_l:
            frame = "future"
        if not frame:
            add_msg(
                "assistant",
                "I'd love to help! Please choose: **Past**, **Present**, or **Future**.",
            )
            return

    icons = {"past": "\U0001f56f\ufe0f", "present": "\U0001f338", "future": "\u2728"}
    if atype == "frame":
        add_msg("user", f"{icons[frame]} {frame.title()}")

    st.session_state.memory_frame = frame
    st.session_state.phase = "asking"
    st.session_state.q_idx = 0
    st.session_state.answers = {}

    add_msg("assistant", FRAME_INTROS[frame])
    ask_next_question()


def _handle_question(action):
    q = get_current_question()
    if not q:
        return

    atype = action.get("type", "text")
    value = action.get("value", "")

    if atype == "single_select":
        add_msg("user", action.get("label", value))
        st.session_state.answers[q["key"]] = value
        st.session_state.q_idx += 1
        ask_next_question()

    elif atype == "multi_done":
        options = q.get("options", [])
        labels = [lbl for v, lbl in options if v in value]
        add_msg("user", ", ".join(labels) if labels else "\u2014")
        st.session_state.answers[q["key"]] = list(value)
        st.session_state._multi_selected = []
        st.session_state.q_idx += 1
        ask_next_question()

    elif atype == "text":
        add_msg("user", value)

        if q["type"] == "text":
            st.session_state.answers[q["key"]] = value
            st.session_state.q_idx += 1
            ask_next_question()

        elif q["type"] == "single":
            m = match_single(value, q["options"])
            if m:
                st.session_state.answers[q["key"]] = m[0]
                st.session_state.q_idx += 1
                ask_next_question()
            else:
                labels = ", ".join(lbl for _, lbl in q["options"])
                add_msg("assistant", f"Please choose from: **{labels}**")

        elif q["type"] == "multi":
            matched = match_multi(value, q["options"])
            if matched:
                st.session_state.answers[q["key"]] = [v for v, _ in matched]
                st.session_state._multi_selected = []
                st.session_state.q_idx += 1
                ask_next_question()
            else:
                labels = ", ".join(lbl for _, lbl in q["options"])
                add_msg(
                    "assistant",
                    f"Please choose from: **{labels}** *(separate multiple with commas)*",
                )


def _handle_free_text(action):
    text = action.get("value", "")
    add_msg("user", text)
    skip_words = {"skip", "no", "none", "n/a", "nope", "nothing", ""}
    st.session_state.free_text = "" if text.lower().strip() in skip_words else text
    add_msg(
        "assistant",
        "Thank you. Let me craft your fragrance now...",
    )
    st.session_state.phase = "generating"


def _handle_result(action):
    text = action.get("value", "")
    text_l = text.lower().strip()

    refinement = None
    if any(w in text_l for w in ("lighter", "softer", "subtle")):
        refinement = "lighter"
    elif any(w in text_l for w in ("stronger", "richer", "deeper", "intense")):
        refinement = "stronger"
    elif any(w in text_l for w in ("warmer", "warm", "vanilla", "amber")):
        refinement = "warmer"
    elif any(w in text_l for w in ("fresher", "fresh", "citrus", "crisp")):
        refinement = "fresher"
    elif any(
        w in text_l
        for w in ("start over", "restart", "reset", "new fragrance", "begin again")
    ):
        add_msg("user", text)
        reset_conversation()
        return
    elif "save" in text_l:
        add_msg("user", text)
        add_msg(
            "assistant",
            "Your blend has been saved! Say **start over** to create a new fragrance anytime.",
        )
        return

    if refinement:
        add_msg("user", text)
        add_msg(
            "assistant",
            f"Refining your fragrance — making it **{REFINEMENT_MAP[refinement].lower()}**...",
        )
        st.session_state._pending_refinement = refinement
        st.session_state.phase = "refining"
    else:
        add_msg("user", text)
        add_msg(
            "assistant",
            "You can refine your fragrance — try saying **lighter**, **stronger**, "
            "**warmer**, or **fresher**. Or say **start over** to create a new one.",
        )


def _process_action(action):
    handlers = {
        "greeting": _handle_greeting,
        "asking": _handle_question,
        "free_text": _handle_free_text,
        "result": _handle_result,
    }
    handler = handlers.get(st.session_state.phase)
    if handler:
        handler(action)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Initialise & Process Pending Action
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if not st.session_state.messages:
    add_msg("assistant", WELCOME_MESSAGE)

if st.session_state._action is not None:
    _act = st.session_state._action
    st.session_state._action = None
    _process_action(_act)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Render UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _on_theme_toggle():
    st.session_state.dark_mode = not st.session_state.dark_mode


# ─── Header ──────────────────────────────────────────────────────────────────

_hcol1, _hcol2 = st.columns([8, 1])
with _hcol1:
    st.markdown(
        '<div class="hdr-left">'
        '<span class="hdr-title">Mémoire de Parfum</span>'
        '<span class="hdr-sub">where memories become fragrance</span>'
        '</div>',
        unsafe_allow_html=True,
    )
with _hcol2:
    _icon = "\u2600\ufe0f" if _dark else "\U0001f319"
    st.button(_icon, key="theme_toggle", on_click=_on_theme_toggle)

st.markdown(
    '<div style="border-bottom:1px solid var(--border);margin-bottom:0.6rem"></div>',
    unsafe_allow_html=True,
)

# ─── Chat messages (custom HTML bubbles) ──────────────────────────────────────

for _msg in st.session_state.messages:
    render_bubble(_msg["role"], _msg["content"], _msg.get("html", False))


# ─── API-call phases (typing indicator while blocking) ────────────────────────

if st.session_state.phase == "generating":
    render_typing(TYPING_HTML_GENERATE)
    try:
        payload = build_payload()
        resp = httpx.post(
            f"{API_BASE}/fragrance/generate",
            json=payload,
            timeout=FRAGRANCE_TIMEOUT,
        )
        if resp.status_code != 200:
            try:
                err = resp.json()
                emsg = err.get("message", err.get("detail", resp.text))
            except Exception:
                emsg = resp.text
            add_msg(
                "assistant",
                f"Something went wrong: {emsg}\n\nSay **start over** to try again.",
            )
            st.session_state.phase = "result"
            st.rerun()

        data = resp.json()
        st.session_state.intent = data["intent"]
        st.session_state.blueprint = data["blueprint"]
        st.session_state.fragrance_story = data["fragrance_story"]
        st.session_state.refinement_count = 0

        add_msg(
            "assistant",
            format_result_html(data["blueprint"], data["fragrance_story"]),
            html=True,
        )
        add_msg(
            "assistant",
            "Here's your fragrance blueprint. You can **refine** it — "
            "try *lighter*, *stronger*, *warmer*, or *fresher*. "
            "Or say **start over** to create something new.",
        )
        st.session_state.phase = "result"
        st.rerun()

    except httpx.TimeoutException:
        add_msg(
            "assistant",
            "The request took too long. Please check that the backend and all "
            "services are running, then say **start over** to try again.",
        )
        st.session_state.phase = "result"
        st.rerun()
    except Exception as exc:
        add_msg(
            "assistant",
            f"Something went wrong: {exc}\n\nSay **start over** to try again.",
        )
        st.session_state.phase = "result"
        st.rerun()

elif st.session_state.phase == "refining":
    refinement = st.session_state._pending_refinement
    if refinement:
        render_typing(TYPING_HTML_REFINE)
        try:
            resp = httpx.post(
                f"{API_BASE}/refine/",
                json={
                    "intent": st.session_state.intent,
                    "refinement": refinement,
                },
                timeout=REFINE_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            st.session_state.intent = data["intent"]
            st.session_state.blueprint = data["blueprint"]
            st.session_state.fragrance_story = data["fragrance_story"]
            st.session_state.refinement_count += 1
            st.session_state._pending_refinement = None

            label = REFINEMENT_MAP[refinement]
            add_msg("assistant", f"Here's your **{label.lower()}** version:")
            add_msg(
                "assistant",
                format_result_html(data["blueprint"], data["fragrance_story"]),
                html=True,
            )
            add_msg(
                "assistant",
                "Want to refine further? Try *lighter*, *stronger*, *warmer*, "
                "or *fresher*. Or say **start over** for a new creation.",
            )
            st.session_state.phase = "result"
            st.rerun()

        except httpx.TimeoutException:
            add_msg(
                "assistant", "The refinement took too long. Please try again."
            )
            st.session_state.phase = "result"
            st.rerun()
        except Exception as exc:
            add_msg("assistant", f"Something went wrong: {exc}")
            st.session_state.phase = "result"
            st.rerun()


# ─── Suggestion chips (above chat input) ─────────────────────────────────────

_phase = st.session_state.phase


def _set_action(a):
    st.session_state._action = a


def _toggle_multi(val):
    sel = st.session_state._multi_selected
    if val in sel:
        sel.remove(val)
    else:
        sel.append(val)


if _phase not in ("generating", "refining"):
    st.markdown('<hr class="suggestion-sep">', unsafe_allow_html=True)

if _phase == "greeting":
    cols = st.columns(3)
    with cols[0]:
        st.button(
            "\U0001f56f\ufe0f Past",
            use_container_width=True,
            on_click=_set_action,
            args=({"type": "frame", "value": "past"},),
        )
    with cols[1]:
        st.button(
            "\U0001f338 Present",
            use_container_width=True,
            on_click=_set_action,
            args=({"type": "frame", "value": "present"},),
        )
    with cols[2]:
        st.button(
            "\u2728 Future",
            use_container_width=True,
            on_click=_set_action,
            args=({"type": "frame", "value": "future"},),
        )

elif _phase == "asking":
    _q = get_current_question()

    if _q and _q["type"] == "single":
        opts = _q["options"]
        n_cols = min(len(opts), 4) if len(opts) <= 4 else 3
        cols = st.columns(n_cols)
        for i, (val, lbl) in enumerate(opts):
            with cols[i % n_cols]:
                st.button(
                    lbl,
                    key=f"q{st.session_state.q_idx}_s_{val}",
                    use_container_width=True,
                    on_click=_set_action,
                    args=({"type": "single_select", "value": val, "label": lbl},),
                )

    elif _q and _q["type"] == "multi":
        opts = _q["options"]
        sel = st.session_state._multi_selected
        n_cols = min(len(opts), 3)
        cols = st.columns(n_cols)
        for i, (val, lbl) in enumerate(opts):
            is_on = val in sel
            with cols[i % n_cols]:
                st.button(
                    f"\u2713 {lbl}" if is_on else lbl,
                    key=f"q{st.session_state.q_idx}_m_{val}",
                    use_container_width=True,
                    on_click=_toggle_multi,
                    args=(val,),
                )
        if sel:
            st.button(
                "Continue \u2192",
                key=f"q{st.session_state.q_idx}_done",
                use_container_width=True,
                on_click=_set_action,
                args=({"type": "multi_done", "value": sel.copy()},),
            )

elif _phase == "free_text":
    st.button(
        "Skip \u2192",
        key="skip_free_text",
        use_container_width=False,
        on_click=_set_action,
        args=({"type": "text", "value": "skip"},),
    )

elif _phase == "result":
    cols = st.columns(4)
    for i, (val, lbl) in enumerate(REFINEMENT_MAP.items()):
        with cols[i]:
            st.button(
                lbl,
                key=f"ref_{val}",
                use_container_width=True,
                on_click=_set_action,
                args=({"type": "text", "value": val},),
            )
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        st.button(
            "Save Blend",
            key="save_blend",
            use_container_width=True,
            on_click=_set_action,
            args=({"type": "text", "value": "save"},),
        )
    with _c2:
        st.button(
            "Start Over",
            key="start_over",
            use_container_width=True,
            on_click=_set_action,
            args=({"type": "text", "value": "start over"},),
        )


# ─── Chat input ──────────────────────────────────────────────────────────────

if _phase not in ("generating", "refining"):
    _placeholders = {
        "greeting": "Or type past, present, or future...",
        "asking": "Type your answer...",
        "free_text": "Share more details, or type 'skip'...",
        "result": "Try: lighter, stronger, warmer, fresher, or start over...",
    }
    if _prompt := st.chat_input(_placeholders.get(_phase, "Type your message...")):
        st.session_state._action = {"type": "text", "value": _prompt}
        st.rerun()
