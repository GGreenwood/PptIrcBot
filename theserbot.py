#!/usr/bin/env python2.7

#IRC and yaml reading bot

import irc.client
import sys
import logging
import re
import yaml
import os
import time
from threading import Thread
import traceback
from Queue import Queue
from subprocess import call

#Setting the global logger to debug gets all sorts of irc debugging
logging.getLogger().setLevel(logging.WARNING)

def debug(msg):
    try:
        print msg
    except UnicodeEncodeError:
        pass


settingsFile = open("settings.yaml")
settings = yaml.load(settingsFile)
settingsFile.close()

IrcServer = settings.get('IrcServer', 'irc.freenode.net')
IrcNick = settings.get('IrcNick', 'TheAxeBot')
IrcPassword = settings.get('IrcPassword', None)
IrcChannel = settings.get('IrcChannel', '#serisium')

ReplayPipeName = settings.get('ReplayPipeName', 'replay_pipe')
TasbotPipeName = settings.get('TasbotPipeName', 'tasbot_pipe')

TasbotPipeEnable = settings.get('TasbotPipeEnable', False)

LeftDelay = settings.get('LeftDelay', 30)
RightDelay = settings.get('RightDelay', 10)

def writeToPipe(writePipe, msg):
    """Utility function to write a message to a pipe.
       First add a newline if it doesn't have one.
       Then write the message and flush the pipe.
    """
    if not msg.endswith('\n'):
        msg += '\n'
    writePipe.write(msg)
    writePipe.flush()


class ReplayTextThread(Thread):
    """This thread grabs strings off the queue and writes them to the
       pipe that the replay script should be reading from.
       This ensures thread safety between the multiple threads that need
       to write to that pipe.
       It will never stop so do not wait for it!
    """
    def __init__(self, replayQueue):
        super(ReplayTextThread, self).__init__()

        self.replayQueue = replayQueue

    def run(self):
        if not os.path.exists(ReplayPipeName):
            os.mkfifo(ReplayPipeName)
        writePipe = open(ReplayPipeName, 'w')
        while True:
            msg = self.replayQueue.get()
            writeToPipe(writePipe, msg)

class PptIrcBot(irc.client.SimpleIRCClient):
    def __init__(self):
        irc.client.SimpleIRCClient.__init__(self)
        #Precompiled tokenizing regex
        self.splitter = re.compile(r'[^\w]+')
        self.replayQueue = Queue()
        self.nonPrintingChars = set([chr(i) for i in xrange(32)])
        self.nonPrintingChars.add(127)
        self.leftFrameCount = 1
        self.re = re.compile(r'^[udlrabxy]$')

    def sendMessage(self, msg):
        # We don't want this showing up in chat:
        msg = re.sub(r'\s*ShiftPalette\s*', ' ', msg)
        if msg.isspace():
            # This message only contained ShiftPalette.
            return
        self.connection.privmsg(IrcChannel, msg)

    def on_welcome(self, connection, event):
        print 'joining', IrcChannel
        connection.join(IrcChannel)

    def on_join(self, connection, event):
        """Fires on joining the channel.
           This is when the action starts.
        """
        if (event.source.find(IrcNick) != -1):
            print "I joined!"
            self.replayThread = ReplayTextThread(self.replayQueue)
            print 'starting replay thread'
            self.replayThread.start()

    def on_disconnect(self, connection, event):
        sys.exit(0)

    def naughtyMessage(self, sender, reason):
        #Be sure to get rid of the naughty message before the event!
        #An easy way is to just make this function a pass
        #pass
        # self.connection.privmsg(IrcChannel, "Naughty %s (%s)" % (sender, reason))
        print("Naughty %s (%s)" % (sender, reason))

    def on_pubmsg(self, connection, event):
        debug("pubmsg from %s: %s" % (event.source, event.arguments[0]))
        text = event.arguments[0]
        sender = event.source.split('!')[0]

        #Check for non-ascii characters
        try:
            text.decode('ascii')
        except (UnicodeDecodeError, UnicodeEncodeError):
            self.naughtyMessage(sender, "not ascii")
            return
        except Exception:
            #I am not sure what else can happen but just to be safe, reject on other errors
            return

        text_lower = text.lower()
        text = text.replace('left', 'l')
        text = text.replace('right', 'r')
        text = text.replace('up', 'u')
        text = text.replace('down', 'd')

        # Enforce left delay
        if text == 'l':
            if self.leftFrameCount > LeftDelay:
                self.leftFrameCount = 1

            else:
                self.naughtyMessage(sender, "left pressed too soon")
                return
        else:
            self.leftFrameCount = self.leftFrameCount + 1

        # Enfore right delay
        if text == 'r':
            if self.rightFrameCount > RightDelay:
                self.rightFrameCount = 1

            else:
                self.naughtyMessage(sender, "right pressed too soon")
                return
        else:
            self.rightFrameCount = self.rightFrameCount + 1

        if not self.re.match(text):
            self.naughtyMessage(sender, "Text is not a valid button")
            return

        print text

        #Check that the text is a valid button press

        self.replayQueue.put(text)


def main():
    if ':' in IrcServer:
        try:
            server, port = IrcServer.split(":")
            port = int(port)
        except Exception:
            print("Error: Bad server:port specified")
            sys.exit(1)
    else:
        server = IrcServer
        port = 6667

    c = PptIrcBot()

    try:
        c.connect(server, port, IrcNick, password=IrcPassword)
    except irc.client.ServerConnectionError as x:
        print(x)
        sys.exit(1)
    c.start()

if __name__ == "__main__":
    main()
