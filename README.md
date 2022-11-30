# pytsm

A VERY basic tool, behaving like a Tivoli Storage Manager, and can be used to store backups on hard disks.

This is intend as a quick fix, in case of problems with a real TSM. The script pyTSM can be used, to help you out and do some simple backups with your existing client configs and monitoring infrastructure.

## Some features:
  - NEW: versioning like in rssnapshot
  - pyTSM parses client configs and does basic handling of "DOMAIN" and "EXCLUDE.DIR" directives
  - preserving hardlinks
  - writing mails in case of problems (not tested in last versions)
  - optional: write logfiles at the clients (adsmsched.log), to make monitoring tools happy (experimental feature)
  
## Limitations:
  - only working for linux clients
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

Then you can run:

```
# pytsm.py -f client.list -m YOUR_EMAIL_ADDRESS -l
```

## run a single backup job


```
# pytsm.py -c client1.org -C /etc/adsm/dsm.sys -d /tape0 -m YOUR_EMAIL_ADDRESS -l
```

## Readme
```
pyTSM (pythons Trusty Storage Manager)

Usage:
python3 pytsm.py (-c client -C dsm_conf -d destination_dir | -f client_list_file) [-l | -m admin_mail | -v versions ]

   -c --client fqdn
      FQDN od IP of a client which should be backuped
   -C --dsmconf dsm_conf
      Path to dsm.sys on the client
   -d --dest destination_dir
      Destination directory where the backup should be stored
   -f --clientfile client_list_file
      A file with the clients and destination_dirs and config_file_paths like:
           "FQDN1 DEST_DIR1 DSMC_CONFIG_FILE1"
           "FQDN2 DEST_DIR2 DSMC_CONFIG_FILE2"
           "server1.org  /tape2  /etc/adsm/dsm.sys"
   -l --log
      Write a adsmsched.log on client.
   -m --mail admin_mail
      In case of errors, write a mail to this address.
   -v --versions number
      Versions to keep (hard-linked)
```
