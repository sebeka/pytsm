#!/usr/bin/python3

import sys
import re      # regular expressions
import getopt  # c-like Command line option parsing
import os
import subprocess
import smtplib
import socket
import time

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
python3 pytsm.py (-c client -C dsm_conf -d destination_dir | -f client_list_file) [-l -m admin_mail]

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
   -m --mail admin_mail
      In case of errors, write a mail to this address.

''')
   sys.exit(1)



def parseArguments():
   givenArgs = {
      "client"           : "",
      "dsmsys"           : "",
      "destdir"          : "",
      "clientlist"       : "",
      "log"              : False,
      "mailto"           : ""
   }
   
   
   try:
      options,arguments = getopt.getopt(sys.argv[1:], 'c:C:d:f:lm:', ['client', 'dsmconf', 'dest', 'clientfile', 'log', 'mailto'])
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
      elif opt[0] in ('-m', '--mail'):
         givenArgs['mailto'] = opt[1]
   
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
   
   return (givenArgs)


def sendmail(mailto, subject, text):
   print (text)
   if (mailto != ""):
      sender = 'root@' + socket.getfqdn()
      receivers = [mailto]
      message = '''From: ''' + sender + '''
To: ''' + mailto + '''
Subject: ''' + subject + '''

''' + text
      try:
         smtpObj = smtplib.SMTP(SMTP_SERVER)
         smtpObj.sendmail(sender, receivers, message)
      #except SMTPException:
      except:
         print('Error: unable to send mail to ' + mailto) 


def parseclientlist(listfile):
   clients = []
   with open(listfile) as file:
      for line in file:
         line = line.strip()
         client = line.split()
         if (len(client) >= 3):
            clients.append(client)
   return(clients)


def getClientconf(client, dsmsys, destdir, mailto):

   domains = []
   excludedirs = []
   logfile = ""
   clientconf = {
      'domains'     : domains,
      'excludedirs' : excludedirs,
      'logfile'     : logfile
   }


   # test if dsm.sys is there
   cmd = ['/usr/bin/ssh', client, 'test -f ' + dsmsys]
   try:
      retval = subprocess.call(cmd)
   except:
      sendmail(mailto, 'Backup failed on ' + client, 'Error: Could not connect to ' + client)
      return False

   if (retval != 0):
      sendmail(mailto, 'Backup failed on ' + client, 'Error: File ' + dsmsys + ' not found on ' + client + ' or could not connect via ssh')
      return False
   # get the content of dsm.sys
   cmd = ['/usr/bin/ssh', client, 'cat ' + dsmsys]
   try:
      output = subprocess.check_output(cmd)
   except:
      sendmail(mailto, 'Backup failed on ' + client, 'Error: Could not connect to ' + client)
      return False

   for line in output.decode('utf8').splitlines():
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



def writelogfile(client, logfile, result, data, mailto):
   print('Writing to ' + logfile + ' on ' + client)
   mailSubject = 'Could not write Backup logfile on ' + client

   # test if logfile is there:
   if (logfile == ""):
      sendmail(mailto, mailSubject, 'No logfile given in dsmc config')
      return False
   cmd = ['/usr/bin/ssh', client, 'test -f ' + logfile]
   try:
      retval = subprocess.call(cmd)
   except:
      sendmail(mailto, mailSubject, 'Error: Could not connect to ' + client)
      return False

   if (retval != 0):
      sendmail(mailto, mailSubject, 'Error: File ' + logfile + ' not found on ' + client + ' or could not connect via ssh')
      return False


   # figure out the right date form from the client
   cmd = '/usr/bin/ssh ' + client + ' "date +%x"'
   try:
      output = subprocess.check_output(
         cmd, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
   except subprocess.CalledProcessError as exc:
      sendmail(mailto, mailSubject, '''Error: Command "''' + cmd + '''" failed:
         ''' + exc.output)
      return False

   date = output.strip()
   #date    = time.strftime("%x")
   #date    = time.strftime("%m/%d/%Y")
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
   cmd = ['/usr/bin/ssh', client, 'echo -e "' + data + '" | tee -a ' + logfile]
   try:
      output = subprocess.check_output(cmd)
   except:
      sendmail(mailto, mailSubject, 'Error: Could not connect to ' + client)
      return False
   #print (output)


def runOneClient(client, dsmsys, destdir, writelog, mailto):
   destdir = destdir + "/" + client
   print("Backup " + client + " to " + destdir + " ...")
   clientConf = getClientconf(client, dsmsys, destdir, mailto)
   if (clientConf == False):
      return
   #print(clientConf)

   if (not os.path.isdir(destdir)):
      os.mkdir(destdir)

   cmd = ['rsync', '-a', '-H', '-x', '--delete', '--numeric-ids', '--stats']
   for domain in clientConf['domains']:
      cmd.append(client + ":" + domain)
   for excludedir in clientConf['excludedirs']:
      cmd.append('--exclude')
      cmd.append(excludedir)
   cmd.append(destdir)
   cmd = ' '.join(cmd)
   print(cmd)
   result = 'completed successfully'
   try:
      output = subprocess.check_output(
         cmd, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
   except subprocess.CalledProcessError as exc:
      sendmail(mailto, 'Backup problem on ' + client, '''Error: Command "''' + cmd + '''" failed:
         ''' + exc.output)
      result = 'failed'

   #print(output)
   if (writelog == True):
      writelogfile(client, clientConf['logfile'], result, output, mailto)



############
# the start
############


givenArgs = parseArguments()
#print(givenArgs)

if (givenArgs['clientlist'] == ""):
   runOneClient(givenArgs['client'], givenArgs['dsmsys'], givenArgs['destdir'], givenArgs['log'], givenArgs['mailto'])
else:
   clients = parseclientlist(givenArgs['clientlist'])
   #print(clients);
   for client in clients:
      if (client[0][0] == '#'):
          continue
      runOneClient(client[0], client[2], client[1], givenArgs['log'], givenArgs['mailto'])


