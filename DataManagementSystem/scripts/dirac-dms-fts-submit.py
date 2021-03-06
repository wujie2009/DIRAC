#! /usr/bin/env python
########################################################################
# $HeadURL:  $
########################################################################
__RCSID__   = "$Id:  $"

from DIRAC.Core.Base import Script

Script.setUsageMessage("""
Submit an FTS request

Usage:
   %s <lfn|fileOfLFN> sourceSE targetSE
""" % Script.scriptName)
 
parseCommandLine()
from DIRAC.DataManagementSystem.Client.FTSRequest     import FTSRequest
import os,sys

if not len(sys.argv) >= 4:
  Script.showHelp()
  DIRAC.exit( -1 )
else:
  inputFileName = sys.argv[1]
  sourceSE = sys.argv[2]
  targetSE = sys.argv[3]

if not os.path.exists(inputFileName):
  lfns = [inputFileName]
else:
  inputFile = open(inputFileName,'r')
  string = inputFile.read()
  inputFile.close()
  lfns = string.splitlines()

oFTSRequest = FTSRequest()
oFTSRequest.setSourceSE(sourceSE)
oFTSRequest.setTargetSE(targetSE)
for lfn in lfns:
  oFTSRequest.setLFN(lfn)
oFTSRequest.submit(monitor=True,printOutput=False)
