import unittest
from facelock.facelock import FaceLock


class FaceLockTestCase(unittest.TestCase):
    def setUp(self):
        self.image1_url = 'https://upload.wikimedia.org/wikipedia/commons/7/7f/Colin_Firth_2009.jpg'
        self.image2_url = 'https://tribzap2it.files.wordpress.com/2013/04/colin-firth-bridget-jones-3-gi.jpg'
        self.facelock = FaceLock(config_file='../facelock/facelock.cfg')

    def test_face_detect_http(self):
        status_code = self.facelock.save_reference_face(self.image1_url)
        self.assertEqual(status_code, 200)
        self.assertEqual(self.facelock.model['image'], self.image1_url)

    def test_face_detect_local(self):
        status_code = self.facelock.save_reference_face('test/resource/colin-firth.jpg')
        self.assertEqual(status_code, 200)

    def test_face_verify(self):
        self.facelock.save_reference_face(self.image1_url)
        confidence = self.facelock.face_verify(self.image2_url)
        self.assertGreater(confidence, 0.5)