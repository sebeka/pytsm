#!/usr/bin/python3

import sys
import re      # regular expressions
import getopt  # c-like Command line option parsing
import os
import subprocess
import smtplib
import socket
import time
import shutil

SMTP_SERVER = 'smtp.org'
STAT_MAPPINGS = [
   {'from' : 'Number of files:' ,                     'to' : 'Total number of objects inspected:      '},
   {'from' : 'Number of regular files transferred:' , 'to' : 'Total number of objects backed up:      '},
   {'from' : 'Number of deleted files:' ,             'to' : 'Total number of objects deleted:        '},
   {'from' : 'Total file size:' ,                     'to' : 'Total number of bytes inspected:        '},
   {'from' : 'Total bytes sent:' ,                    'to' : 'Total number of bytes transferred:      '},
   {'from' : 'File list transfer time:' ,             'to' : 'Data transfer time:                     '}
]

def printUsage():
   print ('''pyTSM (pythons Trusty Storage Manager)

Usage:
python3 pytsm.py (-c client -C dsm_conf -d destination_dir | -f client_list_file) [-l | -v versions | -t]

   -c --client fqdn
      FQDN od IP of a client which should be backuped
   -C --dsmconf dsm_conf
      Path to dsm.sys on the client
   -d --dest destination_dir
      Destination directory where the backup should be stored
   -f --clientfile client_list_file
      A file with the clients and destination_dirs like:
           "FQDN1 DIR1 DSMC_CONFIG_FILE1"
           "FQDN2 DIR2 DSMC_CONFIG_FILE2"
           "server1.org  /tape2  /etc/adsm/dsm.sys"
   -l --log
      Write a adsmsched.log on client.
   -L --Log path to custom log file
      Write logs not to adsmsched.log but to "custom log file".
   -v --versions number
      Versions to keep (hard-linked)
   -t --timestamp
      create a file "rsnapshot.timestamp" in every Domain on the backup-client with the
      current timestamp. (needed for check with check-bkup-versions.py)
''')
   sys.exit(1)



def parseArguments():
   givenArgs = {
      "client"           : "",
      "dsmsys"           : "",
      "destdir"          : "",
      "clientlist"       : "",
      "log"              : False,
      "customlogfile"    : "",
      "versions"         : "1",
      "timestamp"        : False
   }
   
   
   try:
       options,arguments = getopt.getopt(sys.argv[1:], 'c:C:d:f:lL:m:v:t', ['client=', 'dsmconf=', 'dest=', 'clientfile=', 'log=', 'logfile=', 'versions=', 'timestamp='])
   except:
      printUsage()
      sys.exit(1)

   #print(options)
   
   for opt in options:
      if opt[0] in ('-c', '--client'):
         givenArgs['client'] = opt[1]
      elif opt[0] in ('-C', '--dsmconf'):
         givenArgs['dsmsys'] = opt[1]
      elif opt[0] in ('-d', '--dest'):
         givenArgs['destdir'] = opt[1]
      elif opt[0] in ('-f', '--clientfile'):
         givenArgs['clientlist'] = opt[1]
      elif opt[0] in ('-l', '--log'):
         givenArgs['log'] = True
      elif opt[0] in ('-L', '--logfile'):
         givenArgs['customlogfile'] = opt[1]
      elif opt[0] in ('-v', '--versions'):
         givenArgs['versions'] = opt[1]
      elif opt[0] in ('-t', '--timestamp'):
         givenArgs['timestamp'] = True


   if (givenArgs['clientlist'] == ""):
      if (givenArgs['client'] == "" or givenArgs['destdir'] == "" or givenArgs['dsmsys'] == ""):
         print("Error, you have to give either a list of clients \"--clientfile\", or a single client \"-c\" with a path to dsm.sys \"-C\"  and a single destionation folder \"-f\"")
         printUsage()
      if (not os.path.isdir(givenArgs['destdir'])):
         print("Folder " + givenArgs['destdir'] + " not found")
         sys.exit(1)
   else:
      if (not os.path.isfile(givenArgs['clientlist'])):
         print("Folder " + givenArgs['clientlist'] + " not found")
         sys.exit(1)

   if (givenArgs['log'] == True and givenArgs['customlogfile'] != ""):
      print("Error, either \"-l\" or \"-L LOGFILE\" could be used")
      sys.exit(1)

   if (not givenArgs['versions'].isdigit()):
      print("Error, \"versions\" has to be a number > 0")
      sys.exit(1)
   givenArgs['versions'] = int(givenArgs['versions'])
   if (givenArgs['versions'] < 1):
      print("Error, \"versions\" has to be a number > 0")
      sys.exit(1)

   
   return (givenArgs)



def parseClientList(listfile):
   clients = []
   with open(listfile) as file:
      for line in file:
         line = line.strip()
         client = line.split()
         if (len(client) >= 3):
            clients.append(client)
   return(clients)


def execCommand(commandString):
   ret = {
      'stdout' : "",
      'stderr' : "",
      'retval' : 0
   }

   try:
      output = subprocess.check_output(commandString, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
   except subprocess.CalledProcessError as exc:
      ret['stderr'] = exc.output
      ret['retval'] = exc.returncode
   else:
      ret['stdout'] = output
      #print("Output: \n{}\n".format(output))

   return ret




def getClientConf(client, dsmsys):

   domains = []
   excludedirs = []
   logfile = ""
   clientconf = {
      'domains'     : domains,
      'excludedirs' : excludedirs,
      'logfile'     : logfile
   }


   # test if dsm.sys is there
   cmd = '/usr/bin/ssh ' + client + ' test -f ' + dsmsys
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print('Backup failed on ' + client + ' Error: File ' + dsmsys + ' not found on ' + client  + ':' + ret['stderr'])
      return False

   # get the content of dsm.sys
   cmd = '/usr/bin/ssh ' +  client + ' cat ' + dsmsys
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print('Backup failed on ' + client + ' Error: Could not look in ' + dsmsys + ' on ' + client + ':' + ret['stderr'])
      return False

   #for line in output.decode('utf8').splitlines():
   for line in ret['stdout'].splitlines():
      line = line.strip()
      line = line.split()
      if (len(line) >= 2) and (line[0][0] != '*'):
         if (line[0] == 'DOMAIN'):
            domain = re.sub('"', '', line[1])
            if (domain == 'ALL-LOCAL'):
               domain = "/"
            domains.append(domain)
         elif (line[0] == 'EXCLUDE.DIR'):
            excl = re.sub('"', '', line[1])
            excludedirs.append(excl.strip('/'))
         elif (line[0] == 'SCHEDLOGNAME'):
             logfile = re.sub('"', '', line[1])
   clientconf['domains']     = domains
   clientconf['excludedirs'] = excludedirs
   clientconf['logfile']     = logfile
   return (clientconf)


def moveOlder(versions,destdir, client):
   TIMESTAMP = int(time.time())

   # at first, delete oldes version
   oldestFolder = destdir + "/version-" + str(versions - 1) + "/" + client
   if os.path.isdir(oldestFolder):
       shutil.rmtree(oldestFolder)


   if versions > 2:
      # first we have to create a list from (versions - 3) to (0)
      #for i in range ((versions - 2), 0):
      for i in range (0, (versions - 2)):
         version = (versions - i - 2)

         source = destdir + "/version-" + str(version) + "/" + client
         dest   = destdir + "/version-" + str(version + 1) + "/"
         if not os.path.isdir(source):
            # skip if not copied so fas
            continue

         print ("  move " + source + " to " + dest + ' ...')
         cmd = ['mv', source, dest]
         cmd = ' '.join(cmd)
         ret = execCommand(cmd)
         if (ret['retval'] != 0):
            print ('Error: Could not move ' + source + ' to ' + dest + ' : ' + ret['stderr'])
            return False

         # repair the timestamp on dest for the older versions
         os.utime(dest, (TIMESTAMP, TIMESTAMP - ((version + 1) * 3600 * 24)) )


   # copy with hardlinks 0 -> 1
   if os.path.isdir(destdir + "/version-0"):
      print ('  Copy ' + destdir + '/version-0/' + client + ' to ' + destdir + '/version-1/  ...')
      cmd = ['cp', '-l', '-a', destdir + "/version-0/" + client, destdir + "/version-1/"]
      cmd = ' '.join(cmd)
      ret = execCommand(cmd)
      if (ret['retval'] != 0):
         print ('Error: Could cp -l -a ' + destdir + '/version-0/' + client + ' to ' + destdir + '/version-1/ ' + client + ' : ' + ret['stderr'])
         return False;
      os.utime(destdir + '/version-1/' , (TIMESTAMP, TIMESTAMP - (3600 * 24) ))

   return True


def writeLogFile(client, logfile, result, data):
   print('Writing to ' + logfile + ' on ' + client)
   #print(data)

   # test if logfile is there:
   if (logfile == ""):
      print("Error: No logfile given in dsmc config")
      return False
   cmd = '/usr/bin/ssh ' + client + ' "test -f ' + logfile + '"'
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print( 'Error: File ' + logfile + ' not found on ' + client + ':' + ret['stderr'])
      return False

   # figure out the right date form from the client
   cmd = '/usr/bin/ssh ' + client + ' "date +%x"'
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print( 'Error: Could not figure out the date format on ' + client + ':' + ret['stderr'])
      return False

   date = ret['stdout'].strip()
   curtime = time.strftime("%X")
   prefix = date + '   ' + curtime + ' '
   logs = []

   # gather log data
   errors = "0"
   rsyncdata = data.splitlines()
   logs.append(prefix + 'Command will be executed in 0 minutes')
   logs.append(prefix + '--- SCHEDULEREC OBJECT BEGIN pyTSM-01')
   logs.append(prefix + '--- SCHEDULEREC STATUS BEGIN')

   for mapping in STAT_MAPPINGS:
      for line in rsyncdata:
         if (line.startswith(mapping['from'])):
            logs.append(prefix + mapping['to'] + (line[len(mapping['from']):]) )
            continue
         elif (line.startswith('rsync error:')):
            errors = '>0'
   logs.append(prefix + 'Total number of objects failed:          ' + errors)
   logs.append(prefix + '--- SCHEDULEREC STATUS END')
   logs.append(prefix + '--- SCHEDULEREC OBJECT END')
   logs.append(prefix + '--- Scheduled event pyTSM-01 ' + result)
   data = "\n".join(logs)

   # write logfile
   cmd = 'echo "' + data + '" | /usr/bin/ssh ' + client + ' "cat >> ' + logfile + '"'
   print(cmd)
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print ('Error: Could not write to ' + logfile + ' on ' + client + ':' + ret['stderr'] + ':' + ret['stderr'])
      return False


def runOneClient(client, dsmsys, destdir, writelog, writelogToFile, versions, timestamp):
   # get config
   storeIn = destdir + "/version-0/" + client
   print("Backup " + client + " to " + destdir + " ...")
   clientConf = getClientConf(client, dsmsys)
   if (clientConf == False):
      return
   #print(clientConf)

   TIMESTAMP = int(time.time())

   if (versions > 1):
      if not moveOlder(versions,destdir, client):
         if (writelog == True):
            writeLogFile(client, clientConf['logfile'], result, 'Failure during moveOlder')
         if (writelogToFile != ""):
            writeLogFile(client, writelogToFile, result, 'Failure during moveOlder')
         print ('Error: Failure during moveOlder')
         return 


   # create rsnapshot.timestamp files on Server
   if timestamp:
      TIMESTAMP = int(time.time())
      for domain in clientConf['domains']:
         cmd = 'ssh ' + client + ' "echo ' + str(TIMESTAMP) + ' > ' + domain + '/rsnapshot.timestamp"'
         ret = execCommand(cmd)
         if (ret['retval'] != 0):
             print('Error: Could not create rsnapshot.timestamp on ' + client + "/" + domain + ' : ' + ret['stderr'])
             sys.exit(1)

   if (not os.path.isdir(destdir)):
      os.mkdir(destdir)
   if (not os.path.isdir(destdir + "/version-0/")):
      os.mkdir(destdir + "/version-0/")
   if (not os.path.isdir(storeIn)):
      os.mkdir(storeIn)

   cmd = ['rsync', '-a', '-H', '-x', '--delete', '--numeric-ids', '--stats']
   for domain in clientConf['domains']:
      cmd.append(client + ":" + domain)
   for excludedir in clientConf['excludedirs']:
      cmd.append('--exclude')
      cmd.append(excludedir)
   cmd.append(storeIn)
   cmd = ' '.join(cmd)
   print(cmd)
   result = 'completed successfully'
   ret = execCommand(cmd)
   if (ret['retval'] != 0):
      print('Error: Backup problem on ' + client, '''Error: Command "''' + cmd  + '''" failed:
''' + ret['stderr'])
      result = 'failed'
   else:
      TIMESTAMP = int(time.time())
      os.utime(destdir + "/version-0", (TIMESTAMP, TIMESTAMP ))

   #print(ret)
   if (writelog == True):
      writeLogFile(client, clientConf['logfile'], result, ret['stdout'] + ret['stderr'])
   if (writelogToFile != ""):
      writeLogFile(client, writelogToFile, result, ret['stdout'] + ret['stderr'])



############
# the start
############


givenArgs = parseArguments()
#print(givenArgs)

if (givenArgs['clientlist'] == ""):
   runOneClient(givenArgs['client'], givenArgs['dsmsys'], givenArgs['destdir'], givenArgs['log'], givenArgs['customlogfile'], givenArgs['versions'], givenArgs['timestamp'])
else:
   clients = parseClientList(givenArgs['clientlist'])
   #print(clients);
   for client in clients:
      if (client[0][0] == '#'):
          continue
      runOneClient(client[0], client[2], client[1], givenArgs['log'], givenArgs['customlogfile'], givenArgs['versions'], givenArgs['timestamp'])


