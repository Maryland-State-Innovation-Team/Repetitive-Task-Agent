import json


def extract_json_from_model_output(model_output):
    """Extracts JSON object from a string that potentially contains markdown
    code fences.

    Args:
    model_output: A string potentially containing a JSON object wrapped in
        markdown code fences (```json ... ```).

    Returns:
    A Python dictionary representing the extracted JSON object,
    or None if JSON extraction fails.
    """
    try:
        cleaned_output = (
            model_output.replace('```json', '').replace('```', '').strip()
        )
        json_object = json.loads(cleaned_output)
        return json_object
    except json.JSONDecodeError as e:
        msg = f'Error decoding JSON: {e}'
        print(msg)
        return None