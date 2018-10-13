import cv2
import os
import logging as log
import datetime as dt
from time import sleep
import time
import click
import platform
import sys
import tempfile
import configparser
import requests
import pickle
import pathlib
import json

from pid.decorator import pidfile


class FaceLock(object):

    def __init__(self, config_file='facelock.cfg'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.face_detect_headers = {'Content-Type': 'application/octet-stream',
                                    'returnFaceAttributes': 'age,gender,glasses, hair',
                                    'Ocp-Apim-Subscription-Key': self.config['DEFAULT']['KEY1']}

        self.face_verify_headers = {'Content-Type': 'application/json',
                                    'Ocp-Apim-Subscription-Key': self.config['DEFAULT']['KEY1']}

        self.face_detect_endpoint = '/face/v1.0/detect'
        self.face_verify_endpoint = 'face/v1.0/verify'
        self.model = dict()

    def save_reference_face(self, ref_image_data):

        try:
            response = requests.post(url=self.config['DEFAULT']['URL']+self.face_detect_endpoint,
                                     data=ref_image_data,
                                     headers=self.face_detect_headers)
            self.model = json.loads(response.content)[0]
            self.model['time'] = time.time()
            self.model['image'] = ref_image_data
            pickle.dump(self.model, open(self.config['DEFAULT']['MODEL_FILE'], "wb"))

        except requests.ConnectionError as e:
            log.error("failed to connect to %s: s" % (self.config['DEFAULT']['URL']+self.face_detect_endpoint, e))

    def face_verify(self, image_data):
        """
        verify an face image is the same person as one stored earlier
        :param image_data:
        :return:
        """
        try:
            response = requests.post(url=self.config['DEFAULT']['URL']+self.face_detect_endpoint,
                                     data=image_data,
                                     headers=self.face_detect_headers)
            data_dict = dict()
            response_dict = json.loads(response.content)[0]

            data_dict['faceId1'] = response_dict['faceId']
            # reference faceId
            data_dict['faceId2'] = self.model['faceId']

            response2 = requests.post(url=self.config['DEFAULT']['URL']+self.face_verify_endpoint,
                                      data=json.dumps(data_dict),
                                      headers=self.face_verify_headers)
            response_dict2 = json.loads(response2.content)[0]
            return response_dict2['confidence']

        except requests.ConnectionError as e:
            log.error("failed to connect to %s: s" % (self.config['DEFAULT']['URL'], e))

    def refresh_model(self):
        """
        if there is a face image and faceID saved the we don't need to POST API
        otherwise save the info to pickle for later use
        :return: a fresh model (<24 hr old)
        """
        try:
            model = pickle.load(open(self.config['DEFAULT']['MODEL_FILE'], "rb"))
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
        log.basicConfig(level=log.INFO)

        video_capture = cv2.VideoCapture(0)
        anterior = 0
        counter = 0
        trigger = int(delay_seconds/sleep_seconds)

        while True:
            t1 = time.time()
            if not video_capture.isOpened():
                print('Unable to load camera.')
                sleep(3)
                pass

            ret, frame = video_capture.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(50, 50)
            )

            if len(faces) < 1:
                counter += 1
                log.info("[%s] no face detected, counter=%d" % (dt.datetime.now(), counter))

                if counter > trigger:
                    self.lock_screen()

                    if not always:
                        video_capture.release()
                        cv2.destroyAllWindows()
                        sys.exit()

            if anterior != len(faces):
                anterior = len(faces)
                log.info("[%s] faces: %d" % (dt.datetime.now(), len(faces)))
                counter = 0

            if display:
                # Draw a rectangle around the faces
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                # Display the resulting frame
                frame = cv2.resize(frame, (300, 200))
                cv2.imshow('Face Detection', frame)
                cv2.waitKey(200)

            t2 = time.time()
            sleep_time = max(0, sleep_seconds-(t2-t1))
            time.sleep(sleep_time)  # Sleep for x second, discounting the running time of the program


@pidfile(piddir=os.path.join(tempfile.gettempdir(), sys.argv[0]+'.pid'))
@click.command()
@click.option('-t', '--trigger-seconds', default=20,
              help='activate command after this many seconds without detecting a face')
@click.option('--sleep-seconds', help='sleep every this many seconds', default=0.5)
@click.option('--display', help='display a webcam window', is_flag=True, default=False)
@click.option('--always', help='do not exist after screen is locked', is_flag=True, default=False)
def main(trigger_seconds, sleep_seconds, display, always):
    """
    program entry

    :param trigger_seconds:
    :param sleep_seconds:
    :param display:
    :param always:
    :return:
    """
    facelock = FaceLock()
    facelock.face_detect('wei.jpg')
    # facelock.run(trigger_seconds, sleep_seconds, display, always)


if __name__ == '__main__':
    main()
