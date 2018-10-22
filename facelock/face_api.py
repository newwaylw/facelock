import requests
import json
import urllib
import logging as log
import io
import time
from PIL import Image
from urllib.parse import urlparse

log.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%d-%m-%Y:%H:%M:%S', level=log.DEBUG)

API_URL = 'https://uksouth.api.cognitive.microsoft.com'
DETECT_ENDPOINT = '/face/v1.0/detect'
VERIFY_ENDPOINT = '/face/v1.0/verify'


def read_image(image):
    """
    Read an image from local or http url to a byte array
    :param image: path or url string of the image file
    :return: a byte array of the image
    """
    if isinstance(image, str):
        parsed_url = urlparse(image)
        # image input is a http resource
        if parsed_url.scheme == 'http' or parsed_url.scheme == 'https':
            response = urllib.request.urlopen(image)
            data = response.read()
        else:
            # if the image input is a string indicating local file
            with open(image, 'rb') as f:
                data = f.read()

    elif isinstance(image, bytes):
        data = image

    else:
        raise ValueError("input must be a image file url or binary image data")

    return data


def frame2img(frame):
    """
    Convert a frame to image data array
    :param frame:
    :return:
    """
    img = Image.fromarray(frame, 'RGB')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def get_reference_face_model(api_key, ref_image_url):
    """
    Microsoft Cognitive Face Detect API to detect a face from image
    :param api_key: Microsoft Cognitive Face API Key
    :param ref_image_url: reference facial image file or url location
    :return: dictionary containing faceId, faceRectangle etc.
    """

    face_detect_headers = {'returnFaceAttributes': 'age, gender, glasses, hair',
                           'Ocp-Apim-Subscription-Key': api_key}

    parsed_url = urlparse(ref_image_url)
    header = face_detect_headers.copy()
    # http image link
    if parsed_url.scheme == 'http' or parsed_url.scheme == 'https':
        header['Content-Type'] = 'application/json'
        payload = json.dumps({'url': ref_image_url})
    else:
        header['Content-Type'] = 'application/octet-stream'
        payload = read_image(ref_image_url)

    model = dict()
    response = requests.post(url=API_URL + DETECT_ENDPOINT,
                             data=payload,
                             headers=header)

    response.raise_for_status()

    # no face detected
    if response.content == b'[]':
        log.warning('no face detected.')
        raise ValueError("input image has no face!")

    model.update(json.loads(response.content)[0])
    model['time'] = time.time()
    model['image'] = ref_image_url
    log.debug('saving model:{}'.format(model))

    return model


def face_verify(api_key, model, image_data):
    """
    verify an face image is the same person as one stored by 'get_reference_face_model()'

    :param api_key: Microsoft Cognitive Face API Key
    :param model: output of face_detect, dictionary containing faceId of the target face, etc
    :param image_data: the face image byte array to verify
    :return: dictionary containing faceId, faceRectangle etc.
    """
    face_detect_headers = {'returnFaceAttributes': 'age, gender, glasses, hair',
                           'Ocp-Apim-Subscription-Key': api_key,
                           'Content-Type': 'application/octet-stream'}

    face_verify_headers = {'Content-Type': 'application/json',
                           'Ocp-Apim-Subscription-Key': api_key}
    return_dict = {'confidence': 0.0,
                   'faceRectangle': {"width": 0, "height": 0, "left": 0, "top": 0}}

    payload = read_image(image_data)
    response = requests.post(url=API_URL + DETECT_ENDPOINT,
                             data=payload,
                             headers=face_detect_headers)

    response.raise_for_status()

    log.debug('detect response.content={}'.format(json.loads(response.content)))

    # no face detected
    if response.content ==b'[]':
        log.debug('No face detected!')
        return return_dict

    data_dict = dict()
    response_dict = json.loads(response.content)[0]

    data_dict['faceId1'] = response_dict['faceId']
    return_dict['faceId'] = response_dict['faceId']
    return_dict['faceRectangle'] = response_dict['faceRectangle']
    # reference faceId
    data_dict['faceId2'] = model['faceId']

    response_verify = requests.post(url=API_URL + VERIFY_ENDPOINT,
                                    data=json.dumps(data_dict),
                                    headers=face_verify_headers)
    log.debug('verify response.content={}'.format(json.loads(response_verify.content)))
    response_verify.raise_for_status()

    response_dict2 = json.loads(response_verify.content)
    return_dict['confidence'] = response_dict2['confidence']
    return return_dict

    # def refresh_model(self):
    #     """
    #     if there is a face image and faceID saved the we don't need to POST API
    #     otherwise save the info to pickle for later use
    #     :return: a fresh model (<24 hr old)
    #     """
    #     try:
    #         model = self.load_model()
    #         last_detect_time = model['time']
    #         current_time_stamp = time.time()
    #         # the face id returned by the Azure face detect api is valid for 24 hours,
    #         # after that we need to request a new face detect api call
    #         if current_time_stamp - last_detect_time > 24*3600:
    #             r = requests.post(url=self.config['DEFAULT']['URL'] + self.face_detect_endpoint,
    #                               data=model['data'],
    #                               headers=self.face_detect_headers)
    #             model.update(r)
    #
    #         return model
    #     except (OSError, IOError) as e:
    #         return None
