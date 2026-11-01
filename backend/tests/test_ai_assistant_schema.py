import importlib
import warnings

from app.schemas import ai_assistant


def test_ai_assistant_schema_imports_without_protected_namespace_warning() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        importlib.reload(ai_assistant)

    assert not [item for item in caught if 'protected namespace' in str(item.message)]
    assert 'model_ref_set' in ai_assistant.AiRuntimeOut.model_fields
