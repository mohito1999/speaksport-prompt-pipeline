from speaksport_pipeline.generation import assemble_prompt
from speaksport_pipeline.models import PromptSectionBundle


def test_assemble_prompt_uses_canonical_order_and_strips_existing_wrappers() -> None:
    prompt = assemble_prompt(
        PromptSectionBundle(
            core_shell="<core-shell>Identity</core-shell>",
            knowledge_base="Facility facts",
            logic_module="Booking workflow",
            closing_core_shells=["Closing behavior"],
        )
    )

    assert prompt.index("<core-shell>") < prompt.index("<knowledge-base>")
    assert prompt.index("<knowledge-base>") < prompt.index("<logic-module>")
    assert prompt.count("<core-shell>") == 2
    assert "<core-shell>\n\n<core-shell>" not in prompt
    assert prompt.endswith("</core-shell>\n")
