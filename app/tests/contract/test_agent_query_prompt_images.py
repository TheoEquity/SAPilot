import pytest

from aperag.schema.view_models import AgentMessage, File
from aperag.service.prompt_template_service import DEFAULT_AGENT_QUERY_PROMPT, build_agent_query_prompt


@pytest.mark.parametrize(
    ('files', 'has_image'),
    [
        (None, False),
        ([File(id='text', name='notes.txt'), File(id='unnamed')], False),
        ([File(id='text', name='notes.txt'), File(id='screenshot', name='error.PNG')], True),
    ],
)
def test_default_agent_query_prompt_only_adds_image_hints_for_images(files, has_image):
    message = AgentMessage(query='SAP test question', collections=[], files=files)
    rendered = build_agent_query_prompt('test-chat', message, 'user', DEFAULT_AGENT_QUERY_PROMPT)
    assert 'SAP test question' in rendered
    assert ('**Image Files**' in rendered) == has_image
    assert ('**IMAGE CONTEXT PROVIDED**' in rendered) == has_image
