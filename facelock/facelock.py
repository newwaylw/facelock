import cv2
import os
import logging as log
import time
import click
import subprocess
import sys
import tempfile
import configparser
import pickle
import json
from time import sleep
from pid.decorator import pidfile
from face_api import read_image, frame2img, get_reference_face_model, face_verify

log.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                datefmt='%d-%m-%Y:%H:%M:%S', level=log.DEBUG)


class FaceLock(object):

    def __init__(self):

        self.model = dict()

    def save_model(self, file) -> None:
        """
        Serialize model to disk
        :param file: destination file name
        :return: None
        """
        pickle.dump(self.model, open(file, "wb"))

    def load_model(self, model):
        self.model = model

    def load_model_from_disk(self, file) -> None:
        """
        Load pickled model from disk
        :param file: model path
        :return: None
        """
        self.model = pickle.load(open(file, "rb"))

    def execute(self, commands: list) -> None:
        """
        execute commands
        :param commands: a list of commands, each command is a list as passed to subprocess.Popen()
        :return: None
        """
        for command in commands:
            log.debug('executing command:{}'.format(command))
            subprocess.Popen(command)

    def verfity(self, api_key, commands, **kwargs) -> None:
        """

        :param api_key: Microsoft Cognitive Face API Key
        :param commands: list of commands to execute
        :param kwargs: extra params passing from arguments
        :return: None
        """
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        # Find OpenCV version

        video_capture = cv2.VideoCapture(0)
        (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split('.')

        if int(major_ver) < 3:
            fps = video_capture.get(cv2.cv.CV_CAP_PROP_FPS)
            log.debug("Frames per second using video.get(cv2.cv.CV_CAP_PROP_FPS): {0}".format(fps))
        else:
            fps = video_capture.get(cv2.CAP_PROP_FPS)
            log.debug("Frames per second using video.get(cv2.CAP_PROP_FPS) : {0}".format(fps))

        # this is the total frames in this time window
        frames_to_trigger = int(kwargs['trigger_seconds'] * fps)
        frame_id = 0

        while True:
            if not video_capture.isOpened():
                print('Unable to load camera.')
                sleep(3)
                pass

            ret, frame = video_capture.read()
            frame = cv2.resize(frame, (300, 200))
            frame_id += 1

            # sample a frame at interval
            if frame_id % (kwargs['sample_interval'] * fps) == 0:
                log.debug('sampled frame id={}'.format(frame_id))
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
                    log.info('No face detected, counter = {}/{}'.format(frame_id, frames_to_trigger))
                else:
                    img_byte_arr = frame2img(frame)
                    response = face_verify(api_key,
                                           self.model,
                                           img_byte_arr)

                    face_rectangle = response['faceRectangle']
                    confidence = response['confidence']
                    if confidence < kwargs['threshold']:
                        log.info('Matching face detected, counter = {}/{}'.format(frame_id, frames_to_trigger))
                    else:
                        # once the right face is (re) recognised, reset the id
                        frame_id = 0
                        log.info('Your face detected, reset frame_id to {}'.format(frame_id))

                    if kwargs['display']:
                        if confidence >= kwargs['threshold']:
                            x = face_rectangle['left']
                            y = face_rectangle['top']
                            w = face_rectangle['width']
                            h = face_rectangle['height']
                            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # show the webcam window
            if kwargs['display']:
                cv2.imshow('Face Recognition', frame)

             #TODO have a better way to let user quitß
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break

            if frame_id >= frames_to_trigger:
                frame_id = 0
                self.execute(commands)

                if not kwargs['always']:
                    video_capture.release()
                    cv2.destroyAllWindows()
                    sys.exit()


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
    log.info('Reference image from: {} saved'.format(image_location))


@cli.command()
@pidfile(piddir=os.path.join(tempfile.gettempdir(), sys.argv[0]+'.pid'))
@click.option('-t', '--trigger-seconds', default=30,
              show_default=True,
              help='activate command after this many seconds without detecting your face')
@click.option('--threshold', default=0.5,
              show_default=True,
              help='threshold for face recognition')
@click.option('--sample-interval', default=1, type=float, show_default=True,
              help='sample a frame every x seconds')
@click.option('--display', is_flag=True, default=False,
              help='display a webcam window')
@click.option('--always', is_flag=True, default=False, show_default=True,
              help='keep running after screen is locked')
@click.pass_context
def verify(ctx, **kwargs):
    facelock = FaceLock()
    api_key = ctx.obj['DEFAULT']['KEY']
    model_file = ctx.obj['DEFAULT']['MODEL_FILE']
    print(ctx.obj['DEFAULT']['COMMANDS'])
    commands = json.loads(ctx.obj['DEFAULT']['COMMANDS'])
    facelock.load_model_from_disk(model_file)
    facelock.verfity(api_key, commands, **kwargs)


if __name__ == '__main__':
    cli(obj={})
