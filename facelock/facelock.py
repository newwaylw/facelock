import cv2
import os
import logging as log
import time
import click
import platform
import sys
import tempfile
import configparser
import pickle
from time import sleep
from pid.decorator import pidfile
from face_api import read_image, frame2img, get_reference_face_model, face_verify

log.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%d-%m-%Y:%H:%M:%S', level=log.DEBUG)


class FaceLock(object):

    def __init__(self):

        self.model = dict()

    def save_model(self, file):
        pickle.dump(self.model, open(file, "wb"))

    def load_model(self, model):
        self.model = model

    def load_model_from_disk(self, file):
        self.model = pickle.load(open(file, "rb"))

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

    def verfity(self, api_key, **kwargs):
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        video_capture = cv2.VideoCapture(0)
        video_capture.set(cv2.CAP_PROP_FPS, 10)
        frame_rate = video_capture.get(5) #frame rate
        trigger = int(kwargs['trigger_seconds'] / kwargs['sleep_seconds'])
        counter = 0

        while True:
            t1 = time.time()
            if not video_capture.isOpened():
                print('Unable to load camera.')
                sleep(3)
                pass

            frame_id = video_capture.get(1)  # current frame number
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
            # precious API calls
            if len(faces) < 1:
                counter += 1
                log.info('No face detected, counter = {}/{}'.format(counter, trigger))
            else:
                img_byte_arr = frame2img(frame)
                response = face_verify(api_key,
                                       self.model,
                                       img_byte_arr)

                face_rectangle = response['faceRectangle']
                confidence = response['confidence']
                if confidence < kwargs['threshold']:
                    counter += 1
                    log.info('Matching face detected, counter = {}/{}'.format(counter, trigger))
                else:
                    counter = 0
                    log.info('Your face detected, reset counter to {}'.format(counter))

                if kwargs['display'] and confidence >= kwargs['threshold']:
                    x = face_rectangle['left']
                    y = face_rectangle['top']
                    w = face_rectangle['width']
                    h = face_rectangle['height']
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            cv2.imshow('Face Recognition', frame)
            cv2.waitKey(200)

            if counter >= trigger:
                counter = 0
                self.lock_screen()

                if not kwargs['always']:
                    video_capture.release()
                    cv2.destroyAllWindows()
                    sys.exit()

            t2 = time.time()
            sleep_time = max(0, kwargs['sleep_seconds'] - (t2 - t1))
            time.sleep(sleep_time)  # Sleep for x second, discounting the running time of the program


@click.group()
@click.option('-cfg', '--config_file',
              default='facelock.cfg',
              help='config file path')
@click.pass_context
def cli(ctx, config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    ctx.obj = config


@cli.command()
@click.argument('image_location')
@click.pass_context
def train(ctx, image_location):
    facelock = FaceLock()
    api_key = ctx.obj['DEFAULT']['KEY']
    model_file = ctx.obj['DEFAULT']['MODEL_FILE']
    facelock.load_model(get_reference_face_model(api_key, image_location))
    facelock.save_model(model_file)


@cli.command()
@pidfile(piddir=os.path.join(tempfile.gettempdir(), sys.argv[0]+'.pid'))
@click.option('-t', '--trigger-seconds', default=30,
              show_default=True,
              help='activate command after this many seconds without detecting your face')
@click.option('--threshold', default=0.5,
              show_default=True,
              help='threshold for face recognition')
@click.option('--sleep-seconds', default=1, show_default=True,
              help='sleep every this many seconds')
@click.option('--display', is_flag=True, default=False,
              help='display a webcam window')
@click.option('--always', is_flag=True, default=False, show_default=True,
              help='keep running after screen is locked')
@click.pass_context
def verify(ctx, **kwargs):
    facelock = FaceLock()
    api_key = ctx.obj['DEFAULT']['KEY']
    model_file = ctx.obj['DEFAULT']['MODEL_FILE']
    facelock.load_model_from_disk(model_file)
    facelock.verfity(api_key, **kwargs)


if __name__ == '__main__':
    cli(obj={})
