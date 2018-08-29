# -*- coding: utf-8 -*-

import ConfigParser
import datetime
import hashlib
import logging
import multiprocessing
import os
import random
import shlex
import shutil
# Imports
import string
import subprocess
import time
from ConfigParser import SafeConfigParser

# Logging stuff
logging.basicConfig()
global log
log = logging.getLogger()
log.setLevel(logging.DEBUG)


######################## Reception specific funcitons ##########################

def parse_manifest(file):
    parser = SafeConfigParser()
    parser.optionxform = str
    parser.read(file)
    files = {}
    for item, value in parser.items('Files'):
        log.debug(item + ' :: ' + value)
        files[item] = value
    return files


# File reception forever loop
def file_reception_loop(params):
    while True:
        wait_for_file(params)
        time.sleep(10)


# Launch UDPCast to receive a file
def receive_file(filepath, properties):
    log.debug(properties['port'])
    command = "udp-receiver --nosync --mcast-rdv-addr {in_ip} " \
              "--interface {out_iface} --portbase {port} " \
              "-f '{filepath}'" \
              "".format(in_ip=properties['dyode_in']['ip'],
                        out_iface=properties['dyode_out']['iface'],
                        port=properties['port'],
                        filepath=filepath)
    log.debug(command)
    # p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    p = subprocess.Popen(shlex.split(command), shell=False,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = p.communicate()


# File reception function
def wait_for_file(params):
    log.debug('Waiting for file ...')
    log.debug(datetime.datetime.now())
    # YOLO
    log.debug(params)
    # Use a dedicated name for each process to prevent race conditions
    process_name = multiprocessing.current_process().name
    manifest_filename = 'manifest_' + process_name + '.cfg'
    receive_file(manifest_filename, params)
    files = parse_manifest(manifest_filename)
    if len(files) == 0:
        log.error('No file detected')
        return 0
    log.debug('Manifest content : %s' % files)
    for f in files:
        filename = os.path.basename(f)
        temp_file = ''.join(random.SystemRandom().choice(
            string.ascii_uppercase + string.digits) for _ in range(12))
        temp_file = '/tmp/' + temp_file
        log.info('Writing to temp file %s' % temp_file)
        receive_file(temp_file, params)
        log.info('File ' + f + ' received')
        log.debug(datetime.datetime.now())

        temp_hash = hash_file(temp_file)
        log.info('Temp File: {}'.format(temp_hash))
        log.info('Orig File: {}'.format(files[f]))
        if temp_hash != files[f]:
            log.error('Invalid checksum for file ' + f)
            os.remove(temp_file)
            log.error('Calculating next file hash...')
            continue
        else:
            log.info('Hashes match !')
            shutil.move(temp_file, params['out'] + '/' + filename)
            log.info('File ' + filename + ' available at ' + params['out'])
    os.remove(manifest_filename)


################### Send specific functions ####################################

# Send a file using udpcast
def send_file(file, params):
    command = 'udp-sender --async --fec 8x16/64 ' \
              '--max-bitrate {bitrate:0.0f}m ' \
              '--mcast-rdv-addr {out_ip} --mcast-data-addr {out_ip} ' \
              '--portbase {port} --autostart 1 ' \
              "--interface {in_iface} -f '{file}'" \
              ''.format(bitrate=params['bitrate'],
                        out_ip=params['dyode_out']['ip'],
                        port=params['port'],
                        in_iface=params['dyode_in']['iface'],
                        file=file)
    log.debug(command)
    p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    time.sleep(3)  # Sometimes udp-receiver is slow to start up


# List all files recursively
def list_all_files(dir):
    files = []
    for root, directories, filenames in os.walk(dir):
        for directory in directories:
            files.append(os.path.join(root, directory))
        for filename in filenames:
            files.append(os.path.join(root, filename))

    return files


# TODO : Adapt to YAML-parsed params
def parse_config():
    parser = SafeConfigParser()
    parser.optionxform = str
    parser.read('sample.folder')
    params = {}
    for item, value in parser.items('folder'):
        log.debug(item + '::' + value)
        params[item] = value
    return params


def write_manifest(files, manifest_filename):
    config = ConfigParser.RawConfigParser()
    config.optionxform = str
    config.add_section('Files')
    log.debug('Files...')
    log.debug(files)
    for f in files:
        config.set('Files', f, files[f])
        log.debug(f + ' :: ' + files[f])

    with open(manifest_filename, 'wb') as configfile:
        config.write(configfile)


def file_copy(params):
    log.debug('Local copy starting ...')

    files = list_all_files(params[1]['in'])
    log.debug('List of files : ' + str(files))
    if len(files) == 0:
        log.debug('No file detected')
        return 0
    manifest_data = {}

    for f in files:
        manifest_data[f] = hash_file(f)
    log.debug('Writing manifest file')
    # Use a dedicated name for each process to prevent race conditions
    manifest_filename = 'manifest_' + str(params[0]) + '.cfg'
    write_manifest(manifest_data, manifest_filename)
    log.info('Sending manifest file : ' + manifest_filename)

    send_file(manifest_filename, params[1])
    log.debug('Deleting manifest file')
    os.remove(manifest_filename)
    for f in files:
        log.info('Sending ' + f)
        send_file(f, params[1])
        log.info('Deleting ' + f)
        os.remove(f)


########################### Shared functions ###################################

def hash_file(file):
    BLOCKSIZE = 65536
    hasher = hashlib.sha256()
    with open(file, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)

    return hasher.hexdigest()
