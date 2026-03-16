import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.blueprint import FragranceBlueprintJSON
from app.models.intent import ScentIntentJSON
from app.guardrails.grounding_rules import apply_grounding_rules
from app.guardrails.policy_rules import apply_policy_rules, check_experiential_framing
from app.errors.exceptions import LLMSynthesisError


# --- LLM setup ---
llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    temperature=settings.LLM_TEMPERATURE,
    max_tokens=settings.LLM_MAX_TOKENS,
    openai_api_key=settings.OPENAI_API_KEY,
    request_timeout=settings.LLM_REQUEST_TIMEOUT,
)

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a master perfumer crafting deeply personal fragrance stories.
Your role is to translate a fragrance blueprint into a beautiful, emotionally resonant description.

Rules you must follow:
- Always describe effects experientially: use words like "evokes", "feels like", "captures", "conjures"
- NEVER make medical or therapeutic claims
- Always reference the user's specific memory frame (past/present/future)
- Keep descriptions poetic but grounded — reference the actual notes selected
- Always mention the safety note naturally at the end
- Maximum 3 paragraphs
"""),
    ("human", """Memory Frame: {memory_frame}

Fragrance Blueprint:
{blueprint}

Retrieved References (use these to ground your explanation):
{references}

User's Original Memory/Context:
{user_context}

Write a personalized fragrance story for this user based on the blueprint above.
""")
])


def _format_blueprint_for_prompt(blueprint: FragranceBlueprintJSON) -> str:
    """Formats the blueprint into a readable string for the prompt."""
    top = ", ".join([n.name for n in blueprint.top_notes])
    heart = ", ".join([n.name for n in blueprint.heart_notes])
    base = ", ".join([n.name for n in blueprint.base_notes])

    return f"""
Top Notes: {top}
Heart Notes: {heart}
Base Notes: {base}
Intensity: {blueprint.intensity}
Projection: {blueprint.projection}
Longevity: {blueprint.longevity}
Substitutions Applied: {', '.join(blueprint.substitutions_applied) or 'None'}
Safety Note: {blueprint.safety_note}
"""


def _extract_user_context(intent: ScentIntentJSON) -> str:
    """Pulls the most relevant user context from the intent."""
    if intent.free_text_memory:
        return intent.free_text_memory
    if intent.past and intent.past.memory_description:
        return intent.past.memory_description
    if intent.imagery:
        return ", ".join(intent.imagery)
    return "Not provided"


@traceable(name="llm_synthesis")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def synthesize_fragrance_output(
    intent: ScentIntentJSON,
    blueprint: FragranceBlueprintJSON,
    retrieved_references: list[str]
) -> str:
    """
    Takes the fragrance blueprint + retrieved references.
    Generates the final user-facing fragrance story.
    Runs grounding + policy guardrails on the output.
    """
    try:
        # Guardrail 1 — grounding check before generation
        apply_grounding_rules(blueprint, retrieved_references)

        chain = SYNTHESIS_PROMPT | llm

        response = await chain.ainvoke({
            "memory_frame": intent.memory_frame.value,
            "blueprint": _format_blueprint_for_prompt(blueprint),
            "references": "\n".join(retrieved_references),
            "user_context": _extract_user_context(intent),
        })

        output_text = response.content

        # Guardrail 2 — policy check after generation
        apply_policy_rules(output_text)

        # Soft quality check — log if experiential framing is missing
        if not check_experiential_framing(output_text):
            print("[WARNING] Output may lack experiential framing — review recommended")

        # Attach the generated explanation to the blueprint
        blueprint.memory_frame_explanation = output_text
        blueprint.retrieved_references = retrieved_references

        return output_text

    except Exception as e:
        raise LLMSynthesisError(
            message=f"LLM synthesis failed: {str(e)}"
        )

