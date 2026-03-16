import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.intent import ScentIntentJSON, MemoryFrame
from app.errors.exceptions import SignalExtractionError


# --- LLM setup ---
llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    temperature=settings.LLM_TEMPERATURE,
    max_tokens=settings.LLM_MAX_TOKENS,
    openai_api_key=settings.OPENAI_API_KEY,
    request_timeout=settings.LLM_REQUEST_TIMEOUT,
)

parser = PydanticOutputParser(pydantic_object=ScentIntentJSON)

ALLOWED_EMOTIONS = [
    "nostalgia", "love", "peace", "joy", "comfort", "excitement",
    "confident", "calm", "energized", "elegant", "powerful",
    "radiant", "empowered", "grounded",
]

EMOTION_SYNONYMS = {
    "happy": "joy", "happiness": "joy", "cheerful": "joy", "joyful": "joy",
    "relaxed": "calm", "serene": "calm", "tranquil": "calm", "peaceful": "peace",
    "serenity": "peace", "soothing": "peace", "tranquility": "peace",
    "warmth": "comfort", "cozy": "comfort", "safe": "comfort", "comforting": "comfort",
    "romantic": "love", "tender": "love", "affection": "love", "passionate": "love",
    "nostalgic": "nostalgia", "sentimental": "nostalgia", "wistful": "nostalgia",
    "bold": "powerful", "strong": "powerful", "fierce": "powerful", "intense": "powerful",
    "energy": "energized", "lively": "energized", "vibrant": "energized",
    "excited": "excitement", "thrilling": "excitement", "adventurous": "excitement",
    "graceful": "elegant", "refined": "elegant", "sophisticated": "elegant",
    "luminous": "radiant", "glowing": "radiant", "bright": "radiant",
    "empowerment": "empowered", "strength": "empowered",
    "stable": "grounded", "rooted": "grounded", "centered": "grounded",
    "assured": "confident", "self-assured": "confident", "poised": "confident",
    "confidence": "confident",
}

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a master perfumer and emotional intelligence expert.
Your task is to analyze a user's questionnaire answers and extract structured scent signals.

Rules:
- The "emotions" field MUST only contain values from this exact list: {allowed_emotions}
- Select 2-4 emotions that best match the user's input
- Map the user's feelings to the closest allowed emotion (e.g. "happy" → "joy", "relaxed" → "calm")
- "desired_intensity" must be one of: "soft", "gentle", "rich"
- "skin_sensitivity_constraint" must be one of: "very_gentle", "balanced", "expressive"
- Be precise about intensity and environmental context
- Never suggest medically therapeutic effects — only experiential ones

{format_instructions}
"""),
    ("human", """Memory Frame: {memory_frame}

Questionnaire Answers:
{questionnaire_data}

Free Text Memory (optional):
{free_text_memory}

Extract the scent signals from this input and return a structured ScentIntentJSON.
Remember: emotions must ONLY be from: {allowed_emotions}
""")
])


@traceable(name="signal_extraction")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
def _normalize_emotions(emotions: list[str]) -> list[str]:
    """Maps LLM-extracted emotions to the exact vocabulary the Neo4j graph understands."""
    normalized = []
    seen = set()
    for e in emotions:
        e_lower = e.lower().strip()
        if e_lower in ALLOWED_EMOTIONS:
            mapped = e_lower
        elif e_lower in EMOTION_SYNONYMS:
            mapped = EMOTION_SYNONYMS[e_lower]
        else:
            mapped = None
        if mapped and mapped not in seen:
            normalized.append(mapped)
            seen.add(mapped)
    return normalized or ["comfort"]


async def extract_scent_signals(
    memory_frame: MemoryFrame,
    questionnaire_data: dict,
    free_text_memory: str = ""
) -> ScentIntentJSON:
    """
    Takes questionnaire answers and extracts a structured ScentIntentJSON.
    Retries up to 3 times on LLM failure with exponential backoff.
    """
    try:
        chain = EXTRACTION_PROMPT | llm | parser

        result = await chain.ainvoke({
            "memory_frame": memory_frame.value,
            "questionnaire_data": json.dumps(questionnaire_data, indent=2),
            "free_text_memory": free_text_memory or "Not provided",
            "format_instructions": parser.get_format_instructions(),
            "allowed_emotions": ", ".join(ALLOWED_EMOTIONS),
        })

        result.emotions = _normalize_emotions(result.emotions)

        return result

    except Exception as e:
        raise SignalExtractionError(
            message=f"Signal extraction failed: {str(e)}"
        )