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
from pid.decorator import pidfile


class FaceLock(object):

    def __init__(self):
        pass

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
                    sys.exit()

            if anterior != len(faces):
                anterior = len(faces)
                log.info("[%s] faces: $s"%(len(faces), dt.datetime.now()))
                counter = 0

            if display:
                # Draw a rectangle around the faces
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                # Display the resulting frame
                cv2.imshow('Face Detection', frame)
            #
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break

            # Display the resulting frame
            #cv2.imshow('Video', frame)
            time.sleep(sleep_seconds) # Sleep for x second
        # When everything is done, release the capture
        video_capture.release()
        cv2.destroyAllWindows()


@pidfile(piddir=os.path.join(tempfile.gettempdir(), sys.argv[0]+'.pid'))
@click.command()
@click.option('-t', '--trigger-seconds', default=5,
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
    facelock.run(trigger_seconds, sleep_seconds, display, always)


if __name__ == '__main__':
    main()
