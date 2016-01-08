import sys
import os
import time
import re
from threading import Thread
from Queue import Queue


def debug(msg):
    print msg
    pass

NopChar = 0x0000

#************************
#*  Character mappings  *
#************************

# Returns a MSB representation of the SNES button map
def makeCharMap():
    mapping = {}
    mapping.update({
        'b': 0,
        'y': 1,
        'start': 2,
        'select': 3,
        'u': 4,
        'd': 5,
        'l': 6,
        'r': 7,
        'a': 8,
        'x': 9,
        'l_shoulder': 10,
        'r_shoulder': 11
    })
    return mapping


CharMap = makeCharMap()

def encodeChar(chatChar=None):
    # Encode a char as a literal button press
    charId = CharMap.get(chatChar)
    if charId:
        #return 0xFFFF - (1 << 15 - charId)
        return 1 << 15 - charId
    else:
        return NopChar

class TextPipeHandler(Thread):
    """Reads the input from the replay pipe and adds to the line queues.
       Decides when to drop chat if it gets too backed up.
    """
    def __init__(self, chatQueue, pipeName):
        super(TextPipeHandler, self).__init__()

        self.chatQueue = chatQueue

        if not os.path.exists(pipeName):
            os.mkfifo(pipeName)
        self.readPipe = open(pipeName, 'r')

    def readNextLine(self):
        """Read the next line, halting everything until something comes"""
        while True:
            line = self.readPipe.readline()
            #If we read from flushed pipe then wait a moment before moving on
            if line == '':
                time.sleep(0.1)
                continue
            return line.rstrip('\n')

    def run(self):
        """Listen on the pipe. On reading something add it to the appropriate queue"""
        while True:
            line = self.readNextLine()
            debug('chat line: ' + line)
            self.chatQueue.put(line)


class BitStreamer(object):
    """Manages the stream of commands to send"""
    def __init__(self, pipeName=None):
        self.chatQueue = Queue()

        #If we got a pipe name then start the pipe handler thread
        #It will add to the queues as it reads text from chat
        if pipeName is not None:
            pipeThread = TextPipeHandler(self.chatQueue, pipeName)
            pipeThread.start()

        #Translate next line into a list of chars or emotes to send
        self.chatChars = []

    def readChatQueue(self):
        """Grab a line of chat text"""
        if self.chatQueue.empty():
            return
        line = self.chatQueue.get()
        self.chatChars = line
        debug("Parsed chat line: " + str(self.chatChars))

    def getBitsToSend(self):
        """Check our char queues and get the bits to send"""
        #include a chat char
        if(self.chatChars):
            encoded = encodeChar(self.chatChars[0]) 
            debug("Button pressed: %s, %s" % (self.chatChars[0], decodeBits(encoded)))
            self.chatChars = ''

            return encoded & 0xFFFF
        else:
            return NopChar

    def getNextBits(self):
        """Send the next set of bits based on incoming text.
           Red's chat gets priority. We can send a chat char with his.
        """
        #If we have no text from chat or red see if there is more
        #available in the Queue
        if len(self.chatChars) == 0:
            self.readChatQueue()

        #This is the stream that goes to replay
        return self.getBitsToSend()


def decodeBits(bits):
    """Debugging decode of 16 bits. Convert to binary string e.g. 00111011011010101010"""
    return format(bits, '#018b')[2:]


class BitStreamerTestThread(Thread):
    """Tests the BitStreamer by printing out its output"""
    def __init__(self, bs):
        super(BitStreamerTestThread, self).__init__()
        self.bs = bs

    def run(self):
        #For testing we grab an stream input every 1/10 of a second
        for i in xrange(1000):
            time.sleep(0.1)
            # print decodeBits(self.bs.getNextBits())


def main():
    """For testing, display control output"""

    if '--test' in sys.argv:
        import doctest
        res = doctest.testmod()
        # print res
        sys.exit(1 if res.failed else 0)

    bs = BitStreamer('pipe_test')
    thread = BitStreamerTestThread(bs)
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    main()
