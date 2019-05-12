import unittest
from unittest.mock import Mock, patch
from facelock import face_api
import hashlib
import requests


# This method will be used by the mock to replace requests.get
def mocked_requests_post(url, data=None, headers=None):
    class MockResponse:
        def __init__(self, response_data, status_code):
            self.content = response_data
            self.status_code = status_code
            self.raise_for_status = requests.exceptions.HTTPError

    if url == face_api.API_URL + face_api.DETECT_ENDPOINT:
        response_data = b'[{"faceId":"d09048fa-7749-4e44-a396-87fc28e569d5",' \
                        b'"faceRectangle":{"top":203,"left":423,"width":332,"height":332}}]'
        return MockResponse(response_data, 200)


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.image1_url = 'https://upload.wikimedia.org/wikipedia/commons/7/7f/Colin_Firth_2009.jpg'
        self.image1_sha224 = '6f5abaa000099e5bec9d2c88129ab2970741420ef4b682c0af40356b'
        self.image_local = 'test/resource/colin-firth.jpg'
        self.image_local_sha224 = 'fa4e077f9c522f112b2a693ab6b28a8d7131f73fa1f5a4f7914b0bdb'

    def test_read_image_web(self):
           img_data = face_api.read_image(self.image1_url)
           digest = hashlib.sha224(img_data).hexdigest()
           self.assertEqual(digest, self.image1_sha224)

    def test_read_image_local(self):
        img_data = face_api.read_image(self.image_local)
        digest = hashlib.sha224(img_data).hexdigest()
        self.assertEqual(digest, self.image_local_sha224)

    @patch('requests.post', side_effect=mocked_requests_post)
    def test_get_reference_face_model(self, mocked_requests_post):
        model = face_api.get_reference_face_model('some_api_key', self.image_local)
        assert model['faceId'] == 'd09048fa-7749-4e44-a396-87fc28e569d5'

