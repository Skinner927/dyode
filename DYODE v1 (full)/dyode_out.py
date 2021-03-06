# -*- coding: utf-8 -*-
import logging
import multiprocessing

import yaml

import dyode
import modbus
import screen

# Logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def launch_agents(module, properties):
    if properties['type'] == 'folder':
        log.debug('Instantiating a file transfer module :: %s' % module)
        dyode.file_reception_loop(properties)
    elif properties['type'] == 'modbus':
        log.debug('Modbus agent : %s' % module)
        modbus.modbus_master(module, properties)
    elif properties['type'] == 'screen':
        log.debug('Screen sharing : %s' % module)
        screen_process = multiprocessing.Process(name='http_server',
                                                 target=screen.http_server,
                                                 args=(module, properties))
        screen_process.start()


if __name__ == '__main__':
    with open('config.yaml', 'r') as config_file:
        config = yaml.load(config_file)

    # Log infos about the configuration file
    log.info('Loading config file')
    log.info('Configuration name : ' + config['config_name'])
    log.info('Configuration version : ' + str(config['config_version']))
    log.info('Configuration date : ' + str(config['config_date']))

    # Static ARP
    log.info('Dyode input ip : ' + str(config['dyode_in']['ip']) + ' (' + str(
        config['dyode_in']['mac']) + ')')
    log.info(
        'Dyode output ip : ' + str(config['dyode_out']['ip']) + ' (' + str(
            config['dyode_out']['mac']) + ')')

    # Iterate on modules
    modules = config.get('modules')
    for module, properties in modules.iteritems():
        properties['dyode_in'] = config['dyode_in']
        properties['dyode_out'] = config['dyode_out']

        # print module
        log.debug('Parsing "' + module + '"')
        log.debug(
            'Trying to launch a new process for module "' + str(module) + '"')
        p = multiprocessing.Process(name=str(module), target=launch_agents,
                                    args=(module, properties))
        p.start()

    # TODO : Check if all modules are still alive and restart the ones that are not
