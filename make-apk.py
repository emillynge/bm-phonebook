import os
import sys
from subprocess import call
from pythonforandroid.toolchain import main
kwargs = {
    '--private': os.path.abspath('.'),
    '--package': 'org.bm.phonebook',
    '--name': "Your app name",
    '--version': '0.1',
    '--bootstrap': 'sdl2',
    '--requirements': ','.join([
        'sdl2',
        'python3',
        ]),
    '--dist_name': 'testproject',
    '--sdk_dir': '/home/emil/android-sdk-linux/',
    '--ndk_dir': '/home/emil/crystax-ndk/',
    '--android_api': '20'
}

if __name__ == '__main__':

    sys.argv = ['python-for-android', 'apk'] + [k + '=' + v for k, v in kwargs.items()]
    main()
