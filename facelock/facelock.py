import cv2
import os
import logging as log
import datetime as dt
import time
import click
import platform
import sys
import tempfile
import configparser
import requests
import pickle
import json
import urllib
import io
from time import sleep
from urllib.parse import urlparse
from pid.decorator import pidfile
from PIL import Image
from facelock.face_api import save_reference_face, face_verify


class FaceLock(object):

    def __init__(self, config_file='facelock.cfg'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.face_detect_headers = {'returnFaceAttributes': 'age,gender,glasses, hair',
                                    'Ocp-Apim-Subscription-Key': self.config['DEFAULT']['KEY1']}

        self.face_verify_headers = {'Content-Type': 'application/json',
                                    'Ocp-Apim-Subscription-Key': self.config['DEFAULT']['KEY1']}

        self.face_detect_endpoint = '/face/v1.0/detect'
        self.face_verify_endpoint = '/face/v1.0/verify'
        self.model = dict()

    def read_image(self, image):
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

    def save_reference_face(self, ref_image_url):

        parsed_url = urlparse(ref_image_url)
        header = self.face_detect_headers.copy()
        # http image link
        if parsed_url.scheme == 'http' or parsed_url.scheme == 'https':
            header['Content-Type'] = 'application/json'
            payload = json.dumps({'url': ref_image_url})
        else:
            header['Content-Type'] = 'application/octet-stream'
            payload = self.read_image(ref_image_url)

        try:
            response = requests.post(url=self.config['DEFAULT']['URL']+self.face_detect_endpoint,
                                     data=payload,
                                     headers=header)

            # no face detected
            if response.content == b'[]':
                log.warning('no face detected.')
                raise ValueError("input image has no face!")

            self.model = json.loads(response.content)[0]
            self.model['time'] = time.time()
            self.model['image'] = ref_image_url
            log.debug('saving model:', self.model)

            return response.status_code

        except requests.ConnectionError as e:
            log.error("failed to connect to %s: s" % (self.config['DEFAULT']['URL']+self.face_detect_endpoint, e))

    def save_model(self):
        pickle.dump(self.model, open(self.config['DEFAULT']['MODEL_FILE'], "wb"))

    def load_model(self):
        return pickle.load(open(self.config['DEFAULT']['MODEL_FILE'], "rb"))

    def face_verify(self, image_data):
        """
        verify an face image is the same person as one stored earlier
        TODO: this method takes two api call, which is expensive for free account - only 20 api calls per minute.
        TODO: How about use openCV to filter no face senario, and only use the Azure API for correct face?
        :param image_data:
        :return:
        """
        try:
            self.model = self.load_model()
            return_dict = dict()

            payload = self.read_image(image_data)
            header = self.face_detect_headers.copy()
            header['Content-Type'] = 'application/octet-stream'
            response = requests.post(url=self.config['DEFAULT']['URL']+self.face_detect_endpoint,
                                     data=payload,
                                     headers=header)

            response.raise_for_status()

            log.debug('detect response.content={}'.format(json.loads(response.content)))

            data_dict = dict()
            response_dict = json.loads(response.content)[0]

            data_dict['faceId1'] = response_dict['faceId']
            return_dict['faceId'] = response_dict['faceId']
            return_dict['faceRectangle'] = response_dict['faceRectangle']
            # reference faceId
            data_dict['faceId2'] = self.model['faceId']

            response_verify = requests.post(url=self.config['DEFAULT']['URL']+self.face_verify_endpoint,
                                            data=json.dumps(data_dict),
                                            headers=self.face_verify_headers)
            log.debug('verify response.content={}'.format(json.loads(response_verify.content)))
            response_verify.raise_for_status()

            response_dict2 = json.loads(response_verify.content)
            return_dict['confidence'] = response_dict2['confidence']
            return return_dict

        except requests.exceptions.RequestException as e:
            log.error("Error: {1}".format(e.strerror))
        # except requests.ConnectionError as e:
        #     log.error("failed to connect to %s: %s" % (self.config['DEFAULT']['URL'], e))

    def refresh_model(self):
        """
        if there is a face image and faceID saved the we don't need to POST API
        otherwise save the info to pickle for later use
        :return: a fresh model (<24 hr old)
        """
        try:
            model = self.load_model()
            last_detect_time = model['time']
            current_time_stamp = time.time()
            # the face id returned by the Azure face detect api is valid for 24 hours,
            # after that we need to request a new face detect api call
            if current_time_stamp - last_detect_time > 24*3600:
                r = requests.post(url=self.config['DEFAULT']['URL'] + self.face_detect_endpoint,
                                  data=model['data'],
                                  headers=self.face_detect_headers)
                model.update(r)

            return model
        except (OSError, IOError) as e:
            return None

    def lock_screen(self) -> None:
        """
        run screen lock command on different platforms
        :return: None
        """
        os_type = platform.system()
        if os_type == 'Windows':
            import ctypes
            ctypes.windll.user32.LockWorkStation()

        elif os_type == 'Linux':
            os.popen('gnome-screensaver-command --lock > /dev/null &')

        elif os_type == 'Darwin':
            os.popen('/System/Library/CoreServices/Menu\ Extras/user.menu/Contents/Resources/CGSession -suspend')
        else:
            raise Exception('Unsupported OS platform: %s' % os_type)

    def run(self, delay_seconds, sleep_seconds, display, always):
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        video_capture = cv2.VideoCapture(0)
        video_capture.set(cv2.CAP_PROP_FPS, 10)
        frame_rate = video_capture.get(5) #frame rate
        trigger = int(delay_seconds / sleep_seconds)
        counter = 0

        while True:
            t1 = time.time()
            if not video_capture.isOpened():
                print('Unable to load camera.')
                sleep(3)
                pass

            frame_id = video_capture.get(1) # current frame number
            ret, frame = video_capture.read()
            # log.debug('frame rate={}, frame id={}'.format(frame_rate, frame_id))
            frame = cv2.resize(frame, (300, 200))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(25, 25)
            )

            # use openCV's face detection, if there is no face, we don't need to waste
            # API calls
            if len(faces) < 1:
                counter += 1
                log.info('No face detected, counter = {}'.format(counter))
            else:
                img = Image.fromarray(frame, 'RGB')
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()

                response = self.face_verify(img_byte_arr)

                face_rectangle = response['faceRectangle']
                confidence = response['confidence']
                if confidence < float(self.config['DEFAULT']['RECOGNITION_THRESHOLD']):
                    counter += 1
                    log.info('Wrong face detected, counter = {}'.format(counter))
                else:
                    counter = 0
                    log.info('Your face detected, reset counter to {}'.format(counter))

                if display and confidence >= float(self.config['DEFAULT']['RECOGNITION_THRESHOLD']):
                    x = face_rectangle['left']
                    y = face_rectangle['top']
                    w = face_rectangle['width']
                    h = face_rectangle['height']
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow('Face Recognition', frame)
            cv2.waitKey(200)

            if counter > trigger:
                counter = 0
                self.lock_screen()

            t2 = time.time()
            sleep_time = max(0, sleep_seconds - (t2 - t1))
            time.sleep(sleep_time)  # Sleep for x second, discounting the running time of the program


@click.group()
def main():
    log.basicConfig(level=log.DEBUG)

@pidfile(piddir=os.path.join(tempfile.gettempdir(), sys.argv[0]+'.pid'))
@main.command()
@click.option('-t', '--trigger-seconds', default=30,
              help='activate command after this many seconds without detecting your face')
@click.option('--sleep-seconds', help='sleep every this many seconds', default=1)
@click.option('--display', help='display a webcam window', is_flag=True, default=False)
@click.option('--always', help='do not exist after screen is locked', is_flag=True, default=False)
def fit(trigger_seconds, sleep_seconds, display, always):
    """
    program entry

    :param trigger_seconds:
    :param sleep_seconds:
    :param display:
    :param always:
    :return:
    """
    facelock = FaceLock()
    facelock.run(trigger_seconds, sleep_seconds, display, always)


@main.command()
@click.argument('image_location')
def train(image_location):
    facelock = FaceLock()
    facelock.save_reference_face(image_location)
    facelock.save_model()


if __name__ == '__main__':
    main()
