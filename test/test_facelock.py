import unittest
from facelock.face_api import read_image
import hashlib


class APITestCase(unittest.TestCase):
    def setUp(self):
        self.image1_url = 'https://upload.wikimedia.org/wikipedia/commons/7/7f/Colin_Firth_2009.jpg'
        self.image1_sha224 = '6f5abaa000099e5bec9d2c88129ab2970741420ef4b682c0af40356b'
        self.image2_file = 'test/resource/colin-firth.jpg'
        self.image2_sha224 = 'fa4e077f9c522f112b2a693ab6b28a8d7131f73fa1f5a4f7914b0bdb'

    def test_read_image_web(self):
        img_data = read_image(self.image1_url)
        digest = hashlib.sha224(img_data).hexdigest()
        self.assertEqual(digest, self.image1_sha224)

    def test_read_image_local(self):
        img_data = read_image(self.image2_file)
        digest = hashlib.sha224(img_data).hexdigest()
        self.assertEqual(digest, self.image2_sha224)
