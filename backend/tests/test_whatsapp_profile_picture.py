import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.whatsapp.client import update_business_profile_picture


class WhatsAppProfilePictureTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "WHATSAPP_ACCESS_TOKEN": "token",
            "WHATSAPP_PHONE_NUMBER_ID": "phone-id",
            "META_APP_ID": "app-id",
        },
        clear=False,
    )
    @patch("src.whatsapp.client.requests.post")
    def test_uploads_and_applies_profile_picture(self, post):
        session = Mock()
        session.json.return_value = {"id": "upload:session"}
        uploaded = Mock()
        uploaded.json.return_value = {"h": "picture-handle"}
        updated = Mock()
        updated.json.return_value = {"success": True}
        post.side_effect = [session, uploaded, updated]

        with tempfile.NamedTemporaryFile(suffix=".jpg") as image:
            image.write(b"image-bytes")
            image.flush()
            result = update_business_profile_picture(image.name)

        self.assertEqual(result, {"success": True})
        self.assertEqual(post.call_count, 3)
        self.assertEqual(
            post.call_args_list[2].kwargs["json"]["profile_picture_handle"],
            "picture-handle",
        )


if __name__ == "__main__":
    unittest.main()
