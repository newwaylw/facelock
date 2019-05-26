# FaceLock
Execute some commands when your face is not detected! 

[![Build Status](https://dev.azure.com/newway0386/newway/_apis/build/status/newwaylw.facelock?branchName=master)](https://dev.azure.com/newway0386/newway/_build/latest?definitionId=1&branchName=master)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Background
My work place [ComplyAdvantage](https://complyadvantage.com) has this 'policy' that if you leave your laptop unlocked and someone else manage to send an email to the whole company from your account, you then need to buy donuts for the company.

I fell victim on the second day on joining! 

I was so upset that I have to do something, I knew it won't be my last time to get 'donut-ed'. 

## Face Detection vs Face Recognition

I first decided to use openCV's face detection to check for the absence of a face via my front webcam - 
If there is no face detected in X seconds, my screen will lock.

It works, but I am not very satisfied, since it is a face recognition algorithm, any face will do.
If my colleague quickly get in front of my laptop before it locks, then it fails.

So I want face recognition instead. But I certainly don't have millions of faces and the GPU power to train a robust [AlexNet](https://papers.nips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks.pdf) 
or [ResNet](https://arxiv.org/abs/1512.03385). So instead I spent sometime to integrate the [Microsoft Cognitive Face API](https://westus.dev.cognitive.microsoft.com/docs/services/563879b61984550e40cbbe8d/operations/563879b61984550f30395236) to my script. 

## Usage
1. Use Python 3.6+
2. Get a [FREE Microsoft Azure](https://azure.microsoft.com/en-gb/free/) account, and get a API key for Face API
in Cognitive Service.
3. Rename facelock.cfg.template to facelock.cfg, add your KEY value to the file, and add any commands you would like to execute, for detailed usage, refer to [python's subprocess](https://docs.python.org/3/library/subprocess.html), for example, to logout Google services in MacOS:
 ````
 COMMANDS = [["open", "-a", "Google Chrome", "http://accounts.google.com/logout"]]
 ````


4. You need to 'train' a reference face (your face) from an image (JPEG etc), please use a good quality picture showing your front face. The image can be a local file or from the web:
  ````
  python facelock/facelock.py train [OPTIONS] IMAGE_LOCATION

  ````

5. Run:
  ````
  python facelock/facelock.py verify

  ````

If the reference face is absent for a set amount of time, the script will execute a list of commands specified in
the config file.

## Limitations
Microsoft's Free account has a 20 API calls/minute request limit. For Face recognition, it takes two API calls, (Detect + Verify),
that means the maximum sampling per minute is 6.
If you use a more frequent *--sample-interval* value you will get **'Too Many Requests'** Error.

The Face Detect API call returns a faceId, it is valid for 24 hours only, after this, you need to re-run 
````
python facelock/facelock.py train
````
