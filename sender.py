import sys
import fcntl
import socket
import time
import threading
import random
import pickle
from flows import flow


class Sender(object):

    def __init__(self, sourceIP, flowSource = "flows/websearch.txt", destList = [], destPort = 8000, cong = "mintcp"):
        self.IP = sourceIP
        self.flowSource = flowSource 
        self.destList = destList
        self.destPort = destPort
        self.cong = cong

        self.createPrioMap()
        self.removeSelfFromDestList()

    def removeSelfFromDestList(self):
        dests = []
        for IP in self.destList:
            if IP != self.IP:
                dests.append(IP)
        self.destList = dests

    def createFlowObj(self):
        self.flow = flow(self.flowSource)

    def createPrioMap(self):
        val = 65
        self.prioMap = {}
        for i in range(1,17):
            self.prioMap[i] = chr(val)
            val += 1

    def openTCPConnection(self, destIP, destPort):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.connect((destIP, destPort))
        return s

    def bindUDPSocket(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s

    def pickDest(self):
        random.seed()
        i = random.randrange(len(self.destList))
        dest = self.destList[i]
        return dest

    def sendFlow(self, socket, destIP):
        flowSize = self.flow.randomSize()
        toSend = flowSize

        startTime = time.time()
        while toSend > 0:
            priority = self.flow.getPriority(flowSize)

            #first byte is the priority, rest of payload is just zeros
            payload = "0"*1023 
            packet = self.prioMap[priority] + payload

            if self.cong != "none":
                socket.send(packet)
            else:
                socket.sendto(packet, (destIP, self.destPort))

            toSend = toSend - 1 #decrement bytes left to send by 1kb

        FCT = time.time() - startTime
        return (flowSize, FCT)


    def sendRoutine(self):
        #pick random destination
        destIP = self.pickDest()

        if self.cong != "none":
            #open TCP connection to destination
            s = self.openTCPConnection(destIP, self.destPort)
        else:
            s = self.bindUDPSocket()

        #send a random-sized flow to random destination
        (flowSize, FCT) = self.sendFlow(s, destIP)
        s.close()

        return (flowSize, FCT)


def main():

    load = float(sys.argv[1])
    runtime = float(sys.argv[2])
    output = sys.argv[3]

    #DEBUG; set random seed to fixed value so sequence is deterministic
    random.seed(1111)

    #open pickled sender (created by pfabric.py)
    sender = ""
    with open("sender.pkl", "rb") as f:
        sender = pickle.load(f)
    
    sender.createFlowObj()

    #debug; get some member variables
    meanFlowSize = (sender.flow).meanSize()
    bw = 1
    newflow = sender.flow
    priomap = sender.prioMap
    
    outfile = "{}/load{}.txt".format(output, int(load*10))

    # with open(outfile,"w") as f:  #create new outfile (deletes any old data)
    #     f.write("")
    #     f.write("Load: " + str(load) +"\n")
    #     f.write("Runtime: " + str(runtime) + "\n")
    #     f.write("mean flow size: " + str(meanFlowSize) + "\n")
    #     f.write("BW: " + str(bw) + "\n")
    #     f.write("Flow sizes: " + str(newflow.flowSizes) + "\n")
    #     f.write("Flow weights: " + str(newflow.flowWeights) + "\n") 
    #     f.write("Prio map: " + str(priomap) + "\n")
    #     f.write("Dest List: " + str(sender.destList) + "\n")

    #calculate rate (lambda) of the Poisson process representing flow arrivals
    rate = (bw*load*(1000000000) / (meanFlowSize*8.0/1460*1500))
    with open(outfile, "a") as f:
        f.write("Rate: {}\n".format(rate))

    start = time.time()
    while (time.time() - start) < runtime:
        #the inter-arrival time for a Poisson process of rate L is exponential with rate L
        waittime = random.expovariate(rate)
        time.sleep(waittime)

        output = sender.sendRoutine()
        flowSize =  output[0]
        FCT = output[1]
 
        result = "{} {}\n".format(flowSize, FCT)

        #write flowSize and completion time to file named by 'load'
        with open(outfile, "a") as f:
            while True:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB) #lock the file
                    break
                except IOError as e:
                    if e.errno != errno.EAGAIN:                    
                        raise
                    else:
                        time.sleep(0.1)
           
            f.write(result)
            fcntl.flock(f, fcntl.LOCK_UN)

        

if __name__== '__main__':
    main()
    #debug

