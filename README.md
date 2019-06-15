# pytsm

A VERY basic replacement for a Tivoli Storage Manager, which can be used to store backups on hard disks.

This is intend as a quick hack, in case of problems with a real TSM. pyTSM can be used, to help you out and do some simple backups
with your existing client configs and monitoring infrastructure.

## Some features:
  - pyTSM parses client configs and does basic handlich od "DOMAIN" and "EXCLUDE.DIR" directives
  - preserving hardlinks
  - writing mails in case of problems
  - optional writing of logfiles at the client (adsmsched.log), to make monitoring tools happy (experimental feature)
  
## Limitations:
  - storing only ONE version of the data (have to use multiple instances if you like more versions - duplicates the amount of data)
  - only working on linux
  - only useful for replacing "dsmc sched" mode in my opinion
  
## Requirements on the client
  - put a public key of the root user from pyTSM server to /root/.ssh/authorized_keys on the client
  - install packet "rsync"
  - valid dsmc-config file (dsmc.sys for exmaple)
  
## Setting pyTSM up at the server
  - create a private+public key pair for the user root
  - mount some free filesystems for the backups (for exmple /tape0 and /tape1)
  - serve a ssh config for the user root in /root/.ssh/config with the FQDNs of your clients:
```
Host client1.org
    User root
    IdentityFile ~/.ssh/id_rsa_pytsm
Host client2.org
    User root
    IdentityFile ~/.ssh/id_rsa_pytsm
Host client3.org
    User root
    IdentityFile ~/.ssh/id_rsa_pytsm
```
  - serve a file where you list your clients, the destination of the backup and the path to dsmc-config on the client
```
client1.org /tape0   /etc/adsm/dsm.sys
client2.org /tape0   /etc/adsm/dsm.sys
client3.org /tape1   /etc/adsm/dsm.sys
```

## run pyTSM
The best is, to run it as a cronjob. Don't forget to edit the "SMTP_SERVER" line at the top of the script.

Than you can run:

```bash
# pytsm.py -f client.list -m YOUR_EMAIL_ADDRESS -l
```

## run a single backup job


```bash
# pytsm.py -c client1.org -C /etc/adsm/dsm.sys -d /tape0 -m YOUR_EMAIL_ADDRESS -l
```

## Readme
```
pyTSM (pythons Trusty Storage Manager)

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
```
