import unittest
from unittest.mock import Mock, patch

from src.brain.decision_layer import _parse_image_message
from src.brain.image_edit_flow import is_delegation_request, is_image_edit_request
from src.specialists.media.gpt_image_editor import (
    _build_prompt,
    _extension_for,
    _extract_required_copy,
    edit_for_story,
)


class ImageEditIntentTests(unittest.TestCase):
    def test_parses_whatsapp_image_caption(self):
        image_id, instruction = _parse_image_message(
            "__image__:media-123\n__caption__:מיה תערכי יפה ותעלי"
        )
        self.assertEqual(image_id, "media-123")
        self.assertEqual(instruction, "מיה תערכי יפה ותעלי")

    def test_plain_image_remains_backward_compatible(self):
        image_id, instruction = _parse_image_message("__image__:media-123")
        self.assertEqual(image_id, "media-123")
        self.assertEqual(instruction, "")

    def test_detects_natural_hebrew_edit_request(self):
        self.assertTrue(is_image_edit_request("מיה קחי את התמונה ותעלי אותה ערוכה"))
        self.assertFalse(is_image_edit_request("תעלי את התמונה כמות שהיא"))

    def test_trust_means_delegation_not_literal_copy(self):
        self.assertTrue(is_delegation_request("סומכת עלייך, תחליטי את"))


class ImageEditorPromptTests(unittest.TestCase):
    def test_prompt_preserves_identity(self):
        prompt = _build_prompt("תעשי רקע זוהר בצבעי הסטודיו")
        self.assertIn("Preserve every person's identity", prompt)
        self.assertIn("תעשי רקע זוהר בצבעי הסטודיו", prompt)

    def test_prompt_requires_execution_first_creative(self):
        prompt = _build_prompt(
            "סומכת עלייך",
            "Brand: MamaFitness\nBusiness goals: bring new trainees",
        )
        self.assertIn("owner should only need to approve", prompt)
        self.assertIn("NEVER print those phrases", prompt)
        self.assertIn("MamaFitness", prompt)

    def test_extracts_unquoted_copy_after_write_command(self):
        instruction = (
            "מיה יא אלופה תעלי סטורי לב שלי רק תכתבי "
            "מקומות אחרונים לפילאטיס מזרן היום ב20:00 מי באה??"
        )
        self.assertEqual(
            _extract_required_copy(instruction),
            "מקומות אחרונים לפילאטיס מזרן היום ב20:00 מי באה??",
        )

    def test_prompt_locks_explicit_copy_without_extra_words(self):
        prompt = _build_prompt(
            "תעלי סטורי ורק תכתבי מקומות אחרונים לפילאטיס מזרן היום ב20:00 מי באה??"
        )
        self.assertIn("Exact required Hebrew copy (mandatory)", prompt)
        self.assertIn("do not rewrite, shorten, translate, correct", prompt)
        self.assertIn("מקומות אחרונים לפילאטיס מזרן היום ב20:00 מי באה??", prompt)

    def test_supported_extension(self):
        self.assertEqual(_extension_for("image/png"), "png")
        self.assertEqual(_extension_for("image/jpeg; charset=binary"), "jpg")

    @patch("src.specialists.media.gpt_image_editor.upload_image")
    @patch("src.specialists.media.gpt_image_editor.requests.post")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_edit_uploads_generated_preview(self, post, upload):
        response = Mock(status_code=200, headers={"x-request-id": "req-test"})
        response.json.return_value = {"data": [{"b64_json": "ZWRpdGVk"}]}
        post.return_value = response
        upload.return_value = "https://example.com/edited.jpg"

        result = edit_for_story("c291cmNl", "image/jpeg", "תאורה חמה")

        self.assertEqual(result, "https://example.com/edited.jpg")
        request = post.call_args
        self.assertEqual(request.kwargs["data"]["model"], "gpt-image-2")
        self.assertIn("תאורה חמה", request.kwargs["data"]["prompt"])
        upload.assert_called_once()


if __name__ == "__main__":
    unittest.main()
